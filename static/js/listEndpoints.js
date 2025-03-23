document.addEventListener("DOMContentLoaded", function() {
  const searchInput = document.getElementById("searchEndpoint");
  if (searchInput) {
    searchInput.addEventListener("keyup", filterEndpoints);
  }

  // For toggling the headers row
  const viewButtons = document.querySelectorAll(".view-headers-btn");
  viewButtons.forEach(btn => {
    btn.addEventListener("click", toggleHeadersRow);
  });
});

/**
 * Filter the endpoints table by checking every cell in the main row.
 */
function filterEndpoints() {
  const query = this.value.toLowerCase();
  const table = document.getElementById("endpointsTable");
  const rows = table.querySelectorAll("tbody tr");

  // Our rows come in pairs: main row and hidden headers row
  for (let i = 0; i < rows.length; i += 2) {
    const mainRow = rows[i];
    const headersRow = rows[i + 1];
    let matchFound = false;

    // Iterate through each cell in the main row
    for (let j = 0; j < mainRow.cells.length; j++) {
      const cellText = mainRow.cells[j].textContent.toLowerCase();
      if (cellText.includes(query)) {
        matchFound = true;
        break;
      }
    }

    if (matchFound) {
      mainRow.style.display = "";
      headersRow.style.display = "none"; // reset headers row
    } else {
      mainRow.style.display = "none";
      headersRow.style.display = "none";
    }
  }
}

/**
 * Toggle the next row (the headers-row) to show/hide the endpoint's headers.
 */
function toggleHeadersRow(event) {
  const button = event.target;
  const currentRow = button.closest("tr");
  const headersRow = currentRow.nextElementSibling; // the hidden row

  if (headersRow.style.display === "none" || !headersRow.style.display) {
    headersRow.style.display = "table-row";
    button.textContent = "Hide Headers";
  } else {
    headersRow.style.display = "none";
    button.textContent = "View Headers";
  }
}