// filterCommon.js
// Used to provide filtering services on the list pages for test_runs, test_suites and test_cases

document.addEventListener("DOMContentLoaded", function() {
    // Expect an array of configuration objects in window.filterConfigs
    if (!window.filterConfigs || !Array.isArray(window.filterConfigs)) return;
  
    window.filterConfigs.forEach(function(config) {
      // Setup toggle buttons for showing/hiding details
      const toggleButtons = document.querySelectorAll(config.toggleButtonSelector);
      toggleButtons.forEach(function(btn) {
        btn.addEventListener("click", function(event) {
          toggleDetails(event, config);
        });
      });
  
      // Setup search input for filtering table rows
      const searchInput = document.getElementById(config.searchInputId);
      if (searchInput) {
        searchInput.addEventListener("keyup", function() {
          filterRows(this.value.toLowerCase(), config);
        });
      }
    });
  });
  
  /**
   * Toggles the details row for a test case (or similar item).
   * The config allows customizing the toggle button text.
   */
  function toggleDetails(event, config) {
    const button = event.target;
    const mainRow = button.closest("tr");
    const detailsRow = mainRow.nextElementSibling; // Assumes details row immediately follows the main row
  
    if (!detailsRow.style.display || detailsRow.style.display === "none") {
      detailsRow.style.display = "table-row";
      button.textContent = config.hideDetailsText || "Hide Details";
    } else {
      detailsRow.style.display = "none";
      button.textContent = config.viewDetailsText || "View Details";
    }
  }
  
  /**
   * Filters table rows based on the search query.
   * Processes rows in groups (e.g., main row + details row) defined by config.rowGroupSize.
   */
  function filterRows(query, config) {
    const table = document.getElementById(config.tableId);
    if (!table) return;
  
    const rows = table.querySelectorAll("tbody tr");
    const rowGroupSize = config.rowGroupSize || 2;
  
    for (let i = 0; i < rows.length; i += rowGroupSize) {
      const mainRow = rows[i];
      let matchFound = false;
  
      // Check each cell in the main row for a match with the query
      mainRow.querySelectorAll("td").forEach(cell => {
        if (cell.textContent.toLowerCase().includes(query)) {
          matchFound = true;
        }
      });
  
      if (matchFound) {
        mainRow.style.display = "";
        // Optionally keep the details row hidden unless toggled manually
        if (i + 1 < rows.length) rows[i + 1].style.display = "none";
      } else {
        mainRow.style.display = "none";
        if (i + 1 < rows.length) rows[i + 1].style.display = "none";
      }
    }
  }
  