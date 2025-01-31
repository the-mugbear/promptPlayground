// 1. Client-Side Validation
function validateForm(event) {
    const descriptionInput = document.getElementById('description');
    
    // Check if required fields are filled
    if (!descriptionInput.value.trim()) {
      alert('Please fill out the Description field.');
      event.preventDefault(); // Prevent form from submitting
    }
  }
  
  // 2. Filter Existing Test Cases
  function filterTestCases() {
    const query = document.getElementById('tcSearch').value.toLowerCase();
    const items = document.querySelectorAll('.test-case-item');
    items.forEach(item => {
      const text = item.textContent.toLowerCase();
      item.style.display = text.includes(query) ? 'block' : 'none';
    });
  }
  
  // 3. (Optional) Simple tooltip approach
  function initTooltips() {
    const tooltipElements = document.querySelectorAll('.tooltip');
    // This is optional if you handle the CSS :hover. 
    // If you want a more dynamic approach, you could do 
    // event listeners here. For now, the CSS hover is enough.
  }
  
  // On page load
  document.addEventListener('DOMContentLoaded', () => {
    // Attach form validation
    const form = document.getElementById('createSuiteForm');
    if (form) {
      form.addEventListener('submit', validateForm);
    }
  
    // Initialize tooltips if needed
    initTooltips();
  
    // If you want dynamic test case searching
    const searchInput = document.getElementById('tcSearch');
    if (searchInput) {
      searchInput.addEventListener('keyup', filterTestCases);
    }
  });
  