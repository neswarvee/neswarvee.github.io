// Navigation + general behaviour
document.addEventListener('DOMContentLoaded', () => {
  // Smooth scrolling for navigation links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      const href = anchor.getAttribute('href');
      if (!href || href === '#') return;

      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });

  // Navigation background change on scroll
  const nav = document.querySelector('nav');
  if (nav) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 100) {
        nav.classList.add('nav-fixed');
      } else {
        nav.classList.remove('nav-fixed');
      }
    });
  }

  // Mobile menu toggle (only if you add .menu-button / .nav-menu in HTML)
    const menuButton = document.querySelector('.menu-button');
    const navMenu = document.querySelector('.nav-menu');

    if (menuButton && navMenu) {
    menuButton.addEventListener('click', () => {
        // Tailwind's `hidden` class controls visibility on mobile
        navMenu.classList.toggle('hidden');
    });
    }


  // Initialise sliders if any are present
  const sliders = document.querySelectorAll('.slider');
  sliders.forEach(slider => new Slider(slider));

  // Chatbot open/close (Dialogflow iframe handles the conversation itself)
  const container = document.getElementById('chatbot-container');
  const toggle = document.getElementById('chatbot-toggle');
  const close = document.getElementById('chatbot-close');

  if (toggle && container) {
    toggle.addEventListener('click', () => {
      container.classList.toggle('hidden');
    });
  }

  if (close && container) {
    close.addEventListener('click', () => {
      container.classList.add('hidden');
    });
  }
  filterProjects('all');
});

const filterProjects = (category) => {
    const projects = document.querySelectorAll('.project-card');

    projects.forEach(project => {
        const categories = project.dataset.category.split(/\s+/);

        if (category === 'all' || categories.includes(category)) {
            project.style.display = 'block';
            project.classList.add('animate-fade-in');
        } else {
            project.style.display = 'none';
            project.classList.remove('animate-fade-in');
        }
    });

    // Reset all buttons
    document.querySelectorAll(".filter-btn").forEach(btn => {
        btn.classList.remove("bg-blue-600", "text-white");
        btn.classList.add("bg-gray-200", "text-gray-700");
    });

    // Highlight the active button using data-filter
    const activeBtn = document.querySelector(`.filter-btn[data-filter="${category}"]`);
    if (activeBtn) {
        activeBtn.classList.add("bg-blue-600", "text-white");
        activeBtn.classList.remove("bg-gray-200", "text-gray-700");
    }
};



// Image slider functionality (kept in case you add sliders later)
class Slider {
  constructor(sliderElement) {
    this.slider = sliderElement;
    this.slides = this.slider.querySelectorAll('.slide');
    this.currentSlide = 0;
    this.totalSlides = this.slides.length;
    this.isAnimating = false;

    if (this.totalSlides > 0) {
      this.init();
    }
  }

  init() {
    // Add navigation buttons
    const prevButton = document.createElement('button');
    const nextButton = document.createElement('button');
    prevButton.innerHTML = '←';
    nextButton.innerHTML = '→';
    prevButton.classList.add('slider-button', 'prev');
    nextButton.classList.add('slider-button', 'next');

    prevButton.addEventListener('click', () => this.changeSlide(-1));
    nextButton.addEventListener('click', () => this.changeSlide(1));

    this.slider.appendChild(prevButton);
    this.slider.appendChild(nextButton);

    // Initialize first slide
    this.showSlide(0);
    this.addTouchSupport();
  }

  showSlide(index) {
    if (this.isAnimating) return;
    this.isAnimating = true;

    if (index >= this.totalSlides) {
      index = 0;
    } else if (index < 0) {
      index = this.totalSlides - 1;
    }

    const offset = -index * 100;
    const track = this.slider.querySelector('.slides');
    if (track) {
      track.style.transform = `translateX(${offset}%)`;
    }
    this.currentSlide = index;

    setTimeout(() => {
      this.isAnimating = false;
    }, 500);
  }

  changeSlide(direction) {
    this.showSlide(this.currentSlide + direction);
  }

  addTouchSupport() {
    let touchStartX = 0;
    let touchEndX = 0;

    this.slider.addEventListener('touchstart', e => {
      touchStartX = e.changedTouches[0].screenX;
    });

    this.slider.addEventListener('touchend', e => {
      touchEndX = e.changedTouches[0].screenX;
      if (touchStartX - touchEndX > 50) {
        this.changeSlide(1);
      } else if (touchEndX - touchStartX > 50) {
        this.changeSlide(-1);
      }
    });
  }
}
