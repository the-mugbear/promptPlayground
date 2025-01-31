// listTestCases.js

document.addEventListener("DOMContentLoaded", function() {
    // 1. Handle toggling of case details
    const viewButtons = document.querySelectorAll(".view-case-details-btn");
    viewButtons.forEach((btn) => {
      btn.addEventListener("click", toggleCaseDetails);
    });
  
    // 2. Handle search/filter input
    const searchInput = document.getElementById("searchCase");
    if (searchInput) {
      searchInput.addEventListener("keyup", filterCases);
    }
  });
  
  /**
   * Toggles the "case-details-row" for the clicked test case
   */
  function toggleCaseDetails(event) {
    const button = event.target;
    const currentRow = button.closest("tr");
    const detailsRow = currentRow.nextElementSibling; // The hidden row
    
    if (detailsRow.style.display === "none") {
      detailsRow.style.display = "table-row";
      button.textContent = "Hide Details";
    } else {
      detailsRow.style.display = "none";
      button.textContent = "View Details";
    }
  }
  
  /**
   * Filters the rows by the description text
   */
  function filterCases() {
    const query = this.value.toLowerCase();
    const table = document.getElementById("casesTable");
    const rows = table.querySelectorAll("tbody tr");
  
    // We have pairs of rows: the main row and the hidden details row
    for (let i = 0; i < rows.length; i += 2) {
      const caseRow = rows[i];
      const detailsRow = rows[i + 1];
  
      // Assuming description is in the 2nd column (td index 1)
      const descCell = caseRow.querySelectorAll("td")[1];
      const descText = descCell.textContent.toLowerCase();
  
      if (descText.includes(query)) {
        caseRow.style.display = "";
        detailsRow.style.display = "none"; // Hide details if we’re not focusing on it
      } else {
        caseRow.style.display = "none";
        detailsRow.style.display = "none";
      }
    }
  }
  