# backend/crawl_and_index.py
import os, glob, json, re, sys, time
from bs4 import BeautifulSoup
import numpy as np
import faiss
from openai import OpenAI

OUT_DIR = "rag_store"
os.makedirs(OUT_DIR, exist_ok=True)

# ---- NEVER hardcode keys. Use env var. ----
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    sys.exit("OPENAI_API_KEY not set. export OPENAI_API_KEY='sk-...' and retry.")

client = OpenAI(api_key=API_KEY)

def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return text

def chunk(text: str, src: str, max_chars: int = 1200):
    parts = []
    text = text.strip()
    if not text:
        return parts
    for i in range(0, len(text), max_chars):
        ct = text[i:i+max_chars].strip()
        if ct:
            parts.append({"src": src, "content": ct})
    return parts

def build_index():
    # Recursively pick up all HTML in repo root (parent of /backend)
    html_files = glob.glob("../**/*.html", recursive=True)
    if not html_files:
        sys.exit("No HTML files found via ../**/*.html. Check your paths.")

    print(f"Found {len(html_files)} HTML files:")
    for f in html_files:
        print(" -", os.path.relpath(f, start=".."))

    chunks = []
    for file in html_files:
        try:
            with open(file, encoding="utf-8") as f:
                text = clean_text(f.read())
            chunks.extend(chunk(text, os.path.basename(file)))
        except Exception as e:
            print(f"Skipping {file}: {e}")

    # Keep only non-empty chunks (and remember which we embedded)
    kept_chunks = [c for c in chunks if c["content"].strip()]
    if not kept_chunks:
        sys.exit("No non-empty text chunks extracted from HTML. Check your pages.")

    print(f"Total chunks (non-empty): {len(kept_chunks)}")

    # ---- Embed in batches ----
    BATCH = 100
    vecs_list = []
    for i in range(0, len(kept_chunks), BATCH):
        batch = [c["content"] for c in kept_chunks[i:i+BATCH]]
        try:
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )
            if not getattr(resp, "data", None):
                raise RuntimeError("Embeddings API returned no data.")
            vecs_list.extend([d.embedding for d in resp.data])
        except Exception as e:
            print(f"Embedding batch {i}-{i+len(batch)-1} failed: {e}")
            print("Aborting to avoid corrupt index.")
            sys.exit(1)
        time.sleep(0.2)  # gentle rate limiting

    if not vecs_list:
        sys.exit("No embeddings created. Check API key/usage limits.")

    vecs = np.array(vecs_list, dtype="float32")
    if vecs.ndim != 2 or vecs.shape[0] == 0:
        sys.exit(f"Embeddings array shape invalid: {vecs.shape}")

    # Normalize & build FAISS index
    faiss.normalize_L2(vecs)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    faiss.write_index(index, f"{OUT_DIR}/faiss.index")

    # IMPORTANT: Save ONLY the chunks we embedded, so counts match index
    with open(f"{OUT_DIR}/chunks.json", "w", encoding="utf-8") as f:
        json.dump(kept_chunks, f, ensure_ascii=False, indent=2)

    print(f"✅ Indexed {len(kept_chunks)} chunks. FAISS dim={vecs.shape[1]}")

if __name__ == "__main__":
    build_index()
