function toggleDetails(id) {
    const el = document.getElementById(id);
    el.classList.toggle('hidden');
}

// Function to apply filters on the test case tables.
function applyFilters() {
    const attemptSelect = document.getElementById('attempt-filter');
    const dispositionSelect = document.getElementById('disposition-filter');
    
    // Get selected attempt numbers as an array of strings.
    const selectedAttempts = Array.from(attemptSelect.selectedOptions).map(opt => opt.value);
    // Get selected disposition; empty string means "all".
    const selectedDisposition = dispositionSelect.value;
    
    // For each test case details table, filter its rows.
    document.querySelectorAll('tr[data-attempt]').forEach(row => {
        const rowAttempt = row.getAttribute('data-attempt');
        const rowStatus = row.getAttribute('data-status');
        
        // Determine if the row matches the attempt filter.
        let attemptMatch = true;
        if (selectedAttempts.length > 0) {
            attemptMatch = selectedAttempts.includes(rowAttempt);
        }
        
        // Determine if the row matches the disposition filter.
        let statusMatch = true;
        if (selectedDisposition !== "") {
            statusMatch = rowStatus === selectedDisposition;
        }
        
        // Show the row if both conditions are met; otherwise hide it.
        if (attemptMatch && statusMatch) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

document.getElementById('apply-filters').addEventListener('click', applyFilters);