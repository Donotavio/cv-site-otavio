// Theme Switcher
const ThemeManager = {
  STORAGE_KEY: 'portfolio-theme',
  THEME_DARK: 'dark-theme',
  THEME_LIGHT: 'light-theme',

  init() {
    this.toggle = document.getElementById('theme-toggle');
    this.sunIcon = this.toggle?.querySelector('.sun-icon');
    this.moonIcon = this.toggle?.querySelector('.moon-icon');
    
    if (!this.toggle) return;

    this.loadTheme();
    this.attachListeners();
  },

  loadTheme() {
    const savedTheme = localStorage.getItem(this.STORAGE_KEY);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    const theme = savedTheme || (prefersDark ? this.THEME_DARK : this.THEME_LIGHT);
    this.applyTheme(theme, false);
  },

  applyTheme(theme, animate = true) {
    const body = document.body;
    
    if (animate) {
      body.classList.add('theme-transitioning');
    }

    if (theme === this.THEME_LIGHT) {
      body.classList.add(this.THEME_LIGHT);
      body.classList.remove(this.THEME_DARK);
      this.updateIcons(true);
    } else {
      body.classList.add(this.THEME_DARK);
      body.classList.remove(this.THEME_LIGHT);
      this.updateIcons(false);
    }

    localStorage.setItem(this.STORAGE_KEY, theme);

    if (animate) {
      setTimeout(() => {
        body.classList.remove('theme-transitioning');
      }, 400);
    }

    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
  },

  updateIcons(isLight) {
    if (!this.sunIcon || !this.moonIcon) return;
    
    if (isLight) {
      this.sunIcon.style.display = 'none';
      this.moonIcon.style.display = 'block';
    } else {
      this.sunIcon.style.display = 'block';
      this.moonIcon.style.display = 'none';
    }
  },

  toggleTheme() {
    const currentTheme = document.body.classList.contains(this.THEME_LIGHT) 
      ? this.THEME_LIGHT 
      : this.THEME_DARK;
    
    const newTheme = currentTheme === this.THEME_LIGHT 
      ? this.THEME_DARK 
      : this.THEME_LIGHT;
    
    this.applyTheme(newTheme, true);
  },

  attachListeners() {
    this.toggle.addEventListener('click', () => this.toggleTheme());
    
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem(this.STORAGE_KEY)) {
        const theme = e.matches ? this.THEME_DARK : this.THEME_LIGHT;
        this.applyTheme(theme, true);
      }
    });
  }
};

document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
});
