// createTestRun.js

document.addEventListener("DOMContentLoaded", function() {
  // 1) Fetch endpoint details when an endpoint is selected
  const endpointSelect = document.getElementById('endpoint_id');
  if (endpointSelect) {
    endpointSelect.addEventListener('change', async function(e) {
      const endpointId = e.target.value;
      if (!endpointId) return;
      try {
        // Example route: /endpoints/<id>/json (ensure this route exists in your Flask app)
        const resp = await fetch(`/endpoints/${endpointId}/json`);
        const data = await resp.json();

        // Populate the payload textarea
        const payloadTextarea = document.getElementById('endpointPayload');
        payloadTextarea.value = data.http_payload || '';

        // Populate the headers container
        const headersContainer = document.getElementById('headersContainer');
        headersContainer.innerHTML = ''; // clear previous headers
        (data.headers || []).forEach(hdr => {
          const row = document.createElement('div');
          row.classList.add('header-row');
          row.innerHTML = `
            <input type="text" class="header-key" name="header_key" value="${hdr.key}">
            <input type="text" class="header-value" name="header_value" value="${hdr.value}">
          `;
          headersContainer.appendChild(row);
        });
      } catch (err) {
        console.error("Failed to load endpoint:", err);
        alert("Error loading endpoint data. See console for details.");
      }
    });
  }

  // 2) Simple "find & replace" for the payload
  function findReplacePayload() {
    const payloadTextarea = document.getElementById('endpointPayload');
    if (!payloadTextarea.value.trim()) {
      alert("No payload to edit.");
      return;
    }
    const findStr = prompt("Find:");
    if (!findStr) return;
    const replaceStr = prompt("Replace with:");
    if (replaceStr === null) return; // user clicked cancel
    payloadTextarea.value = payloadTextarea.value.split(findStr).join(replaceStr);
  }

  // 3) Simple "find & replace" for headers
  function findReplaceHeaders() {
    const headerKeys = document.querySelectorAll('.header-key');
    const headerValues = document.querySelectorAll('.header-value');
    if (!headerKeys.length) {
      alert("No headers to edit.");
      return;
    }
    const findStr = prompt("Find:");
    if (!findStr) return;
    const replaceStr = prompt("Replace with:");
    if (replaceStr === null) return; // user clicked cancel
    headerKeys.forEach(input => {
      input.value = input.value.split(findStr).join(replaceStr);
    });
    headerValues.forEach(input => {
      input.value = input.value.split(findStr).join(replaceStr);
    });
  }

  // 4) Handle test suite selection
  const addSelectedBtn = document.getElementById('addSelectedBtn');
  if (addSelectedBtn) {
    addSelectedBtn.addEventListener('click', () => {
      const checkboxes = document.querySelectorAll('.suite-checkbox:checked');
      const selectedSuitesList = document.getElementById('selectedSuitesList');
      const hiddenSuitesContainer = document.getElementById('hiddenSuitesContainer');
      checkboxes.forEach(cb => {
        // Create a list item for display
        const li = document.createElement('li');
        li.textContent = cb.dataset.description;
        selectedSuitesList.appendChild(li);

        // Create a hidden input for the suite ID
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = 'suite_ids';
        hidden.value = cb.value;
        hiddenSuitesContainer.appendChild(hidden);

        // Uncheck the checkbox to prevent re-adding
        cb.checked = false;
      });
    });
  }

  // 5) AJAX-based search form submission to update the right panel only
  const searchForm = document.querySelector('.search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', function(e) {
      e.preventDefault(); // Prevent full page reload
      const formData = new FormData(searchForm);
      const searchQuery = formData.get('search');
      const url = `${searchForm.action}?search=${encodeURIComponent(searchQuery)}`;
      const rightPanel = document.querySelector('.right-panel');
      rightPanel.innerHTML = '<p>Loading...</p>';

      fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
      .then(response => response.text())
      .then(html => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newRightPanel = doc.querySelector('.right-panel');
        if (newRightPanel) {
          rightPanel.innerHTML = newRightPanel.innerHTML;
        } else {
          rightPanel.innerHTML = html;
        }
      })
      .catch(error => {
        console.error('Error fetching search results:', error);
        rightPanel.innerHTML = '<p>Error loading search results.</p>';
      });
    });
  }

  // 6) AJAX pagination to prevent page reload on page change
  const paginationContainer = document.querySelector(".pagination-links");
  if (paginationContainer) {
    paginationContainer.addEventListener("click", function(e) {
      if (e.target.tagName.toLowerCase() === "a") {
        e.preventDefault();
        const url = e.target.getAttribute("href");
        fetch(url, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.text())
        .then(html => {
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, 'text/html');
          const newSuitesList = doc.querySelector('.suites-list');
          const newPaginationLinks = doc.querySelector('.pagination-links');
          const currentSuitesList = document.querySelector('.suites-list');
          const currentPaginationLinks = document.querySelector('.pagination-links');
          if (currentSuitesList && newSuitesList) {
            currentSuitesList.innerHTML = newSuitesList.innerHTML;
          }
          if (currentPaginationLinks && newPaginationLinks) {
            currentPaginationLinks.innerHTML = newPaginationLinks.innerHTML;
          }
        })
        .catch(err => console.error("AJAX pagination error:", err));
      }
    });
  }

  // Expose find/replace functions globally if needed
  window.findReplacePayload = findReplacePayload;
  window.findReplaceHeaders = findReplaceHeaders;
});
