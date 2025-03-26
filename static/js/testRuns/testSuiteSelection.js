// testSuiteSelection.js
document.addEventListener("DOMContentLoaded", function() {
  // Select the right card container instead of the old right-panel class.
  const rightCard = document.querySelector('.right-card');
  
  if (rightCard) {
    rightCard.addEventListener('click', function(e) {
      // Check if the clicked element is the "Add Selected Suites" button by its id.
      if (e.target && e.target.id === 'addSelectedBtn') {
        // Gather all the checked checkboxes representing selected test suites.
        const checkboxes = document.querySelectorAll('.suite-checkbox:checked');
        // Get the container on the left panel where the selected suites will be displayed.
        const selectedSuitesList = document.getElementById('selectedSuitesList');
        // Get the container where hidden inputs for each suite ID will be added.
        const hiddenSuitesContainer = document.getElementById('hiddenSuitesContainer');
        
        checkboxes.forEach(cb => {
          // Create a list item to display the test suite's description.
          const li = document.createElement('li');
          li.textContent = cb.dataset.description;
          selectedSuitesList.appendChild(li);
          
          // Create a hidden input element for the test suite's ID.
          const hiddenInput = document.createElement('input');
          hiddenInput.type = 'hidden';
          hiddenInput.name = 'suite_ids';
          hiddenInput.value = cb.value;
          hiddenSuitesContainer.appendChild(hiddenInput);
          
          // Uncheck the checkbox after processing.
          cb.checked = false;
        });
      }
    });
  }
});
