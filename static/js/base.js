// base.js

document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.querySelector(".nav-toggle");
  const navLinks = document.querySelector(".nav-links");

  if (toggleBtn && navLinks) {
    toggleBtn.addEventListener("click", () => {
      navLinks.classList.toggle("show-nav");

      // Optionally animate the hamburger lines:
      const hamburger = toggleBtn.querySelector(".hamburger");
      hamburger.classList.toggle("active");
    });
  }
});


document.addEventListener('DOMContentLoaded', function () {
  const closeButtons = document.querySelectorAll('.close-alert');
  closeButtons.forEach(button => {
    button.addEventListener('click', function () {
      this.closest('.alert').style.display = 'none';
    });
  });

  const flashMessages = document.querySelectorAll('.flash-messages .alert');
  const dismissDelay = 5000;
  const fadeDuration = 500;
  flashMessages.forEach(message => {
    setTimeout(() => {
      message.style.transition = `opacity ${fadeDuration}ms ease`;
      message.style.opacity = '0';
      setTimeout(() => {
        message.style.display = 'none';
      }, fadeDuration);
    }, dismissDelay);
  });
});

(function () {
  const themeOriginalLink = document.getElementById('theme-original');
  const themeInspiredLink = document.getElementById('theme-inspired');
  const toggleButton = document.getElementById('theme-toggle');
  const localStorageKey = 'selectedTheme';

  if (!themeOriginalLink || !themeInspiredLink) {
    console.error("Theme CSS link tags not found. Theme toggling disabled.");
    return;
  }
  if (!toggleButton) {
    console.warn("Theme toggle button not found in footer. Toggling disabled.");
  }

  function applyTheme(themeName) {
    console.log(`Attempting to apply theme: ${themeName}`);
    try {
      if (themeName === 'inspired') {
        themeOriginalLink.disabled = true;
        themeInspiredLink.disabled = false;
        console.log("Applied Inspired Theme");
      } else {
        themeOriginalLink.disabled = false;
        themeInspiredLink.disabled = true;
        console.log("Applied Original Theme");
      }
      localStorage.setItem(localStorageKey, themeName);
    } catch (error) {
      console.error("Error applying theme:", error);
      themeOriginalLink.disabled = false;
      themeInspiredLink.disabled = true;
    }
  }

  function toggleTheme() {
    const isOriginalActive = !themeOriginalLink.disabled;
    const nextTheme = isOriginalActive ? 'inspired' : 'original';
    applyTheme(nextTheme);
  }

  const savedTheme = localStorage.getItem(localStorageKey) || 'original';
  applyTheme(savedTheme);

  if (toggleButton) {
    toggleButton.addEventListener('click', toggleTheme);
  }
})();

