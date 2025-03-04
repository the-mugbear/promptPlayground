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
* Filters the rows by matching the query against data from any column.
*/
function filterCases() {
  const query = this.value.toLowerCase();
  const table = document.getElementById("casesTable");
  const rows = table.querySelectorAll("tbody tr");

  // Process rows in pairs: the main row and its corresponding details row
  for (let i = 0; i < rows.length; i += 2) {
    const caseRow = rows[i];
    const detailsRow = rows[i + 1];

    // Check all cells in the main row for a match
    const cells = caseRow.querySelectorAll("td");
    let matchFound = false;
    cells.forEach(cell => {
      if (cell.textContent.toLowerCase().includes(query)) {
        matchFound = true;
      }
    });

    if (matchFound) {
      caseRow.style.display = "";
      // Keep details row hidden unless manually toggled
      detailsRow.style.display = "none";
    } else {
      caseRow.style.display = "none";
      detailsRow.style.display = "none";
    }
  }
}
