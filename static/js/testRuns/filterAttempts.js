function toggleDetails(id) {
    const el = document.getElementById(id);
    el.classList.toggle('hidden');
}

// Function to apply filters on the test case tables.
function applyFilters() {
    // Get all checked attempt checkboxes.
    const attemptCheckboxes = document.querySelectorAll('input[name="attempt_filter"]:checked');
    // Map their values to an array.
    const selectedAttempts = Array.from(attemptCheckboxes).map(cb => cb.value).filter(val => val !== "");
    
    // Get selected disposition; empty string means "all".
    const dispositionSelect = document.getElementById('disposition-filter');
    const selectedDisposition = dispositionSelect.value;
    
    // Get all test case groups
    const testCaseGroups = document.querySelectorAll('.test-case-group');
    
    testCaseGroups.forEach(group => {
        // Get the details section for this group
        const detailsId = group.querySelector('.test-case-details').id;
        const detailsSection = document.getElementById(detailsId);
        
        // Get all rows in this test case group
        const rows = detailsSection.querySelectorAll('tr[data-attempt]');
        let hasVisibleRows = false;
        
        // Check each row in the group
        rows.forEach(row => {
            const rowAttempt = row.getAttribute('data-attempt');
            const rowStatus = row.getAttribute('data-status');
            
            // If no specific attempt is selected, then match all.
            let attemptMatch = selectedAttempts.length === 0 ? true : selectedAttempts.includes(rowAttempt);
            let statusMatch = selectedDisposition === "" ? true : (rowStatus === selectedDisposition);
            
            // Show/hide the row based on filters
            const shouldShow = attemptMatch && statusMatch;
            row.style.display = shouldShow ? "" : "none";
            
            // If any row is visible, mark the group as having visible rows
            if (shouldShow) {
                hasVisibleRows = true;
            }
        });
        
        // Show/hide the entire test case group based on whether it has any visible rows
        group.style.display = hasVisibleRows ? "" : "none";
        
        // If the group is visible and has visible rows, make sure the details section is visible
        if (hasVisibleRows) {
            detailsSection.classList.remove('hidden');
        }
    });
}

// Add event listener for the apply filters button
document.getElementById('apply-filters').addEventListener('click', applyFilters);

// Add event listener for the "All" checkbox to handle its behavior
document.getElementById('attempt_filter_all').addEventListener('change', function() {
    const allCheckbox = this;
    const otherCheckboxes = document.querySelectorAll('input[name="attempt_filter"]:not(#attempt_filter_all)');
    
    if (allCheckbox.checked) {
        // If "All" is checked, uncheck all other checkboxes
        otherCheckboxes.forEach(cb => cb.checked = false);
    } else if (!Array.from(otherCheckboxes).some(cb => cb.checked)) {
        // If no other checkbox is checked, prevent unchecking "All"
        allCheckbox.checked = true;
    }
});

// Add event listeners for individual attempt checkboxes
document.querySelectorAll('input[name="attempt_filter"]:not(#attempt_filter_all)').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
        const allCheckbox = document.getElementById('attempt_filter_all');
        const otherCheckboxes = document.querySelectorAll('input[name="attempt_filter"]:not(#attempt_filter_all)');
        
        if (this.checked) {
            // If any individual checkbox is checked, uncheck "All"
            allCheckbox.checked = false;
        } else if (!Array.from(otherCheckboxes).some(cb => cb.checked)) {
            // If no individual checkbox is checked, check "All"
            allCheckbox.checked = true;
        }
    });
});
