// ajaxSearch.js
document.addEventListener("DOMContentLoaded", function() {
  const searchForm = document.querySelector('.search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', function(e) {
      e.preventDefault(); // Prevent full page reload

      const formData = new FormData(searchForm);
      const searchQuery = formData.get('search');
      const url = `${searchForm.action}?search=${encodeURIComponent(searchQuery)}`;
      const rightCard = document.querySelector('.right-card');
      
      if (rightCard) {
        rightCard.innerHTML = '<p>Loading...</p>';
      }
      
      fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
      .then(response => response.text())
      .then(html => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newRightCard = doc.querySelector('.right-card');
        if (rightCard) {
          rightCard.innerHTML = newRightCard ? newRightCard.innerHTML : html;
        }
      })
      .catch(error => {
        console.error('Error fetching search results:', error);
        if (rightCard) {
          rightCard.innerHTML = '<p>Error loading search results.</p>';
        }
      });
    });
  }
});
