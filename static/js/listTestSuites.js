// listTestSuites.js

document.addEventListener("DOMContentLoaded", function () {
    // 1. Handle 'View Test Cases' button clicks
    const buttons = document.querySelectorAll(".view-test-cases-btn");
    buttons.forEach((btn) => {
      btn.addEventListener("click", toggleTestCasesRow);
    });
  
    // 2. If there's a search input, set up filter logic
    const searchInput = document.getElementById("searchSuite");
    if (searchInput) {
      searchInput.addEventListener("keyup", filterSuites);
    }
  });
  
  /**
   * Toggle the display of the test-cases-row that follows the button's parent row
   */
  function toggleTestCasesRow(event) {
    const button = event.target;
    // The button is inside the row for the suite, so find the next row
    const currentRow = button.closest("tr");
    const testCasesRow = currentRow.nextElementSibling;
  
    if (testCasesRow.style.display === "none") {
      testCasesRow.style.display = "table-row";
      button.textContent = "Hide Test Cases";
    } else {
      testCasesRow.style.display = "none";
      button.textContent = "View Test Cases";
    }
  }
  
  /**
   * Filters the rows in the table based on the user's input
   */
  function filterSuites() {
    const query = this.value.toLowerCase();
    const table = document.getElementById("suitesTable");
    const rows = table.querySelectorAll("tbody tr");
  
    // Because we have pairs of rows (the suite row + the hidden test-cases-row),
    // we want to filter the "suite" rows only, then hide their sibling as well.
    for (let i = 0; i < rows.length; i += 2) {
      const suiteRow = rows[i];
      const testCasesRow = rows[i + 1];
  
      // Let's assume the suite description is in the 2nd column (td index = 1)
      const descriptionCell = suiteRow.querySelectorAll("td")[1];
      const descriptionText = descriptionCell.textContent.toLowerCase();
  
      // Decide if it matches the query
      if (descriptionText.includes(query)) {
        suiteRow.style.display = "";
        testCasesRow.style.display = "none"; // reset to hidden by default
      } else {
        suiteRow.style.display = "none";
        testCasesRow.style.display = "none";
      }
    }
  }
  