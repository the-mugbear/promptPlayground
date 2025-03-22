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
    
    // For each table row in the test case details, filter based on data attributes.
    document.querySelectorAll('tr[data-attempt]').forEach(row => {
        const rowAttempt = row.getAttribute('data-attempt');
        const rowStatus = row.getAttribute('data-status');
        
        // If no specific attempt is selected, then match all.
        let attemptMatch = selectedAttempts.length === 0 ? true : selectedAttempts.includes(rowAttempt);
        let statusMatch = selectedDisposition === "" ? true : (rowStatus === selectedDisposition);
        
        // Show the row if both conditions are met; otherwise hide it.
        row.style.display = (attemptMatch && statusMatch) ? "" : "none";
    });
}

document.getElementById('apply-filters').addEventListener('click', applyFilters);
