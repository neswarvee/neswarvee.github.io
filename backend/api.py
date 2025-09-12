"""
FastAPI backend for your portfolio chatbot.

- Loads FAISS index + chunks built by crawl_and_index.py
- Embeds the user query with `text-embedding-3-small`
- Searches top-k chunks and asks `gpt-4o-mini` to answer
- Returns reply + structured citations (src filename, URL, snippet, score)

Env vars:
  OPENAI_API_KEY   -> required
  SITE_BASE_URL    -> optional (default: https://neswarvee.github.io/)
"""

import os
import sys
import json
from typing import List, Dict, Any

import numpy as np
import faiss
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openai import OpenAI

# ---------- Config ----------
STORE_DIR = "rag_store"
INDEX_PATH = os.path.join(STORE_DIR, "faiss.index")
CHUNKS_PATH = os.path.join(STORE_DIR, "chunks.json")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    sys.exit("OPENAI_API_KEY not set. export OPENAI_API_KEY='sk-...' and retry.")

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://neswarvee.github.io/").rstrip("/")

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- Load index + chunks ----------
if not (os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH)):
    sys.exit("Index not found. Run backend/crawl_and_index.py first.")

index = faiss.read_index(INDEX_PATH)
with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    CHUNKS: List[Dict[str, Any]] = json.load(f)

if index.ntotal != len(CHUNKS):
    sys.exit(f"Index/chunks mismatch: index has {index.ntotal} vectors, chunks has {len(CHUNKS)}.")

# ---------- FastAPI app ----------
app = FastAPI(title="Portfolio Chat API", version="1.0.0")

# CORS: keep wide-open while prototyping; restrict to your domain in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # e.g., ["https://neswarvee.github.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatIn(BaseModel):
    message: str
    history: List[Dict[str, str]] = []   # optional future use

def src_to_url(src: str) -> str:
    """Map a saved 'src' (e.g., 'nhs-powerapps.html') to a public URL."""
    s = (src or "").strip().lstrip("/")
    if s.lower() in ("index.html", "index.htm", ""):
        return f"{SITE_BASE_URL}/"
    return f"{SITE_BASE_URL}/{s}"

def embed_text(text: str) -> np.ndarray:
    """Return L2-normalized embedding vector (1, dim)."""
    r = client.embeddings.create(model="text-embedding-3-small", input=[text])
    v = np.array(r.data[0].embedding, dtype="float32")[None, :]
    faiss.normalize_L2(v)
    return v

def search(query: str, k: int = 5):
    """Return top-k chunks with distances."""
    qv = embed_text(query)
    D, I = index.search(qv, min(k, index.ntotal))
    results = []
    for rank, (idx, score) in enumerate(zip(I[0], D[0]), start=1):
        if idx < 0:
            continue
        c = CHUNKS[idx]
        results.append({
            "id": rank,
            "src": c.get("src", "index.html"),
            "url": src_to_url(c.get("src", "")),
            "snippet": c.get("content", "")[:220] + ("…" if len(c.get("content","")) > 220 else ""),
            "score": float(score),
        })
    return results

@app.get("/health")
def health():
    return {"ok": True, "chunks": len(CHUNKS), "vectors": index.ntotal}

@app.post("/chat")
def chat(body: ChatIn):
    # 1) Retrieve context
    hits = search(body.message, k=5)
    context_blocks = []
    for h in hits:
        # Find original chunk again to include fuller text (shortened in snippet)
        # Use the first match on src + snippet prefix
        for c in CHUNKS:
            if c.get("src") == h["src"] and c.get("content","").startswith(h["snippet"][:-1] if h["snippet"].endswith("…") else h["snippet"]):
                context_blocks.append(f"[{h['id']}] SRC: {h['src']} | URL: {h['url']}\n{c['content'][:900]}")
                break

    context_text = "\n\n".join(context_blocks) if context_blocks else "(no context found)"

    # 2) Ask the model
    sys_prompt = (
        "You are a helpful assistant for the site neswarvee.github.io. "
        "Answer concisely using the provided context. If helpful, reference sources "
        "using [1], [2], etc and include the page name or section. If unsure, say so and "
        "suggest likely sections to visit."
    )
    user_msg = (
        f"User question: {body.message}\n\n"
        f"Site context:\n{context_text}\n\n"
        "Cite sources as [n] where n matches the brackets above."
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
    )
    reply = resp.choices[0].message.content

    return {
        "reply": reply,
        "cites": hits,  # [{id, src, url, snippet, score}]
    }
