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
        // You can define .hamburger.active in your CSS 
        // to transform the lines into an 'X'
      });
    }
  });
  