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
   * Filter the endpoints table by hostname or endpoint 
   */
  function filterEndpoints() {
    const query = this.value.toLowerCase();
    const table = document.getElementById("endpointsTable");
    const rows = table.querySelectorAll("tbody tr");
  
    // Our rows come in pairs: main row, hidden headers row
    // We'll skip the headers row in filtering logic or hide them if the main row doesn't match
    for (let i = 0; i < rows.length; i += 2) {
      const mainRow = rows[i];
      const headersRow = rows[i + 1];
  
      const hostnameCell = mainRow.cells[1]; // Hostname is col #1
      const pathCell = mainRow.cells[2];     // Endpoint path is col #2
  
      const hostnameText = hostnameCell.textContent.toLowerCase();
      const pathText = pathCell.textContent.toLowerCase();
  
      if (hostnameText.includes(query) || pathText.includes(query)) {
        mainRow.style.display = "";
        headersRow.style.display = "none"; // reset
      } else {
        mainRow.style.display = "none";
        headersRow.style.display = "none";
      }
    }
  }
  
  /**
   * Toggle the next row (the headers-row) to show/hide the endpoint's headers
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
  