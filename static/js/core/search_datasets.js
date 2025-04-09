// Client-side filtering for dataset references.
document.addEventListener("DOMContentLoaded", function() {
    const searchInput = document.getElementById('dataset-search');
    const datasetList = document.getElementById('dataset-references-list');
    
    // When the user types in the search bar, filter the list.
    searchInput.addEventListener('keyup', function() {
      const query = this.value.toLowerCase();
      // Get all list items.
      const refs = datasetList.querySelectorAll('.dataset-reference');
      refs.forEach(ref => {
        const text = ref.textContent.toLowerCase();
        // If the text includes the query, display the item; otherwise hide it.
        if (text.includes(query)) {
          ref.style.display = "";
        } else {
          ref.style.display = "none";
        }
      });
    });
  });