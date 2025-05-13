// pagination.js
document.addEventListener("DOMContentLoaded", function() {
  const paginationContainer = document.querySelector(".pagination-links");
  if (paginationContainer) {
    paginationContainer.addEventListener("click", function(e) {
      if (e.target.tagName.toLowerCase() === "a") {
        e.preventDefault();
        const url = e.target.getAttribute("href");
        fetch(url, {
          headers: { 
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrfToken
          }
        })
        .then(response => response.text())
        .then(html => {
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, 'text/html');
          const newSuitesList = doc.querySelector('.suites-list');
          const newPaginationLinks = doc.querySelector('.pagination-links');
          
          const currentSuitesList = document.querySelector('.suites-list');
          const currentPaginationLinks = document.querySelector('.pagination-links');
          
          if (currentSuitesList && newSuitesList) {
            currentSuitesList.innerHTML = newSuitesList.innerHTML;
          }
          if (currentPaginationLinks && newPaginationLinks) {
            currentPaginationLinks.innerHTML = newPaginationLinks.innerHTML;
          }
        })
        .catch(err => console.error("AJAX pagination error:", err));
      }
    });
  }
});
