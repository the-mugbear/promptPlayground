document.addEventListener("DOMContentLoaded", function() {
  // Select the right card container.
  const rightCard = document.querySelector('.right-card');
  
  if (rightCard) {
    rightCard.addEventListener('click', function(e) {
      if (e.target && e.target.id === 'addSelectedBtn') {
        const checkboxes = document.querySelectorAll('.suite-checkbox:checked');
        const selectedSuitesList = document.getElementById('selectedSuitesList');
        const hiddenSuitesContainer = document.getElementById('hiddenSuitesContainer');
        
        checkboxes.forEach(cb => {
          // Use suite id as identifier.
          const suiteId = cb.value;
          // Check if this suite has already been added.
          if (!selectedSuitesList.querySelector(`li[data-suite-id="${suiteId}"]`)) {
            // Create a list item to display the test suite's description.
            const li = document.createElement('li');
            li.setAttribute('data-suite-id', suiteId);
            li.style.display = 'flex';
            li.style.justifyContent = 'space-between';
            li.style.alignItems = 'center';
            
            const span = document.createElement('span');
            span.textContent = cb.dataset.description;
            li.appendChild(span);
            
            // Create a remove button.
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.textContent = '✕';
            removeBtn.style.marginLeft = '1rem';
            removeBtn.addEventListener('click', function() {
              // Remove the list item.
              li.remove();
              // Remove the corresponding hidden input.
              const hiddenInput = hiddenSuitesContainer.querySelector(`input[value="${suiteId}"]`);
              if (hiddenInput) {
                hiddenInput.remove();
              }
            });
            li.appendChild(removeBtn);
            
            selectedSuitesList.appendChild(li);
            
            // Create a hidden input element for the test suite's ID.
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'suite_ids';
            hiddenInput.value = suiteId;
            hiddenSuitesContainer.appendChild(hiddenInput);
          }
          // Uncheck the checkbox after processing.
          cb.checked = false;
        });
      }
    });
  }
});