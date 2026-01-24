// Expor reveal observer globalmente para controle durante scroll da timeline
let revealObserver = null;

const setupRevealAnimations = () => {
  const reveals = document.querySelectorAll('.reveal');
  if (!reveals.length) return;

  // Desconectar observer anterior se existir
  if (revealObserver) {
    revealObserver.disconnect();
  }

  revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('active');
        }
      });
    },
    {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    }
  );

  reveals.forEach((el) => revealObserver.observe(el));
  
  // Expor globalmente para controle durante scroll da timeline
  window.revealObserver = revealObserver;
};

const animateCounters = () => {
  const counters = document.querySelectorAll('.counter');
  if (!counters.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const counter = entry.target;
          const target = parseInt(counter.dataset.target || counter.textContent.replace(/\D/g, ''));
          const duration = 2000;
          const step = target / (duration / 16);
          let current = 0;

          const updateCounter = () => {
            current += step;
            if (current < target) {
              counter.textContent = Math.floor(current).toLocaleString();
              requestAnimationFrame(updateCounter);
            } else {
              counter.textContent = target.toLocaleString();
            }
          };

          updateCounter();
          observer.unobserve(counter);
        }
      });
    },
    { threshold: 0.5 }
  );

  counters.forEach((counter) => observer.observe(counter));
};

const setupCustomCursor = () => {
  if (window.innerWidth < 768) return;

  const cursor = document.createElement('div');
  cursor.className = 'custom-cursor';
  document.body.appendChild(cursor);

  let mouseX = 0;
  let mouseY = 0;
  let cursorX = 0;
  let cursorY = 0;

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    cursor.classList.add('active');
  });

  document.addEventListener('mouseleave', () => {
    cursor.classList.remove('active');
  });

  document.addEventListener('mousedown', () => {
    cursor.classList.add('click');
  });

  document.addEventListener('mouseup', () => {
    cursor.classList.remove('click');
  });

  const animateCursor = () => {
    const speed = 0.15;
    cursorX += (mouseX - cursorX) * speed;
    cursorY += (mouseY - cursorY) * speed;
    cursor.style.left = cursorX + 'px';
    cursor.style.top = cursorY + 'px';
    requestAnimationFrame(animateCursor);
  };

  animateCursor();

  const interactiveElements = document.querySelectorAll('a, button, .card, .tech-item');
  interactiveElements.forEach((el) => {
    el.addEventListener('mouseenter', () => {
      cursor.style.transform = 'scale(1.5)';
    });
    el.addEventListener('mouseleave', () => {
      cursor.style.transform = 'scale(1)';
    });
  });
};

const setupThemeToggle = () => {
  const themeToggle = document.getElementById('theme-toggle');
  if (!themeToggle) return;

  const currentTheme = localStorage.getItem('theme') || 'dark';
  if (currentTheme === 'light') {
    document.body.classList.add('light-theme');
  }

  themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('light-theme');
    const newTheme = document.body.classList.contains('light-theme') ? 'light' : 'dark';
    localStorage.setItem('theme', newTheme);

    const icon = themeToggle.querySelector('svg use');
    if (icon) {
      icon.setAttribute('href', newTheme === 'light' ? '#icon-moon' : '#icon-sun');
    }
  });
};

const initAnimations = () => {
  setupRevealAnimations();
  animateCounters();
  setupCustomCursor();
  setupThemeToggle();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAnimations);
} else {
  initAnimations();
}

window.addEventListener('contentUpdated', () => {
  setupRevealAnimations();
  animateCounters();
});
