// typewriter.js: Typewriter animation logic

document.addEventListener("DOMContentLoaded", function () {
    const text = "Hello, Retro Hacker World!";
    const speed = 100; // ms per character
    let index = 0;
  
    function type() {
      const el = document.getElementById("typewriter");
      if (!el) return; // If element doesn't exist, do nothing
  
      if (index < text.length) {
        el.innerHTML += text.charAt(index);
        index++;
        setTimeout(type, speed);
      } else {
        // Optional: once finished, show a blinking cursor
        el.insertAdjacentHTML("beforeend", "<span class='cursor'></span>");
      }
    }
  
    type();
  });
  