// 1) When the user selects an endpoint, fetch its details via AJAX (you'll need an endpoint that returns JSON).
document.getElementById('endpoint_id').addEventListener('change', async function (e) {
const endpointId = e.target.value;
if (!endpointId) return;

try {
    // Example route: /endpoints/<id>/json
    // You will need to create such a route in your Flask code.
    const resp = await fetch(`/endpoints/${endpointId}/json`);
    const data = await resp.json();

    // Populate the payload textarea
    const payloadTextarea = document.getElementById('endpointPayload');
    payloadTextarea.value = data.http_payload || '';

    // Populate the headers
    const headersContainer = document.getElementById('headersContainer');
    headersContainer.innerHTML = ''; // clear previous
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

// 2) Simple “find & replace” for the payload
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
// Replace all occurrences
payloadTextarea.value = payloadTextarea.value.split(findStr).join(replaceStr);
}

// 3) Simple “find & replace” for headers
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

// Below is existing JS logic to handle test suite selection, etc.
// e.g., in your createTestRun.js
const addSelectedBtn = document.getElementById('addSelectedBtn');
if (addSelectedBtn) {
addSelectedBtn.addEventListener('click', () => {
    const checkboxes = document.querySelectorAll('.suite-checkbox:checked');
    const selectedSuitesList = document.getElementById('selectedSuitesList');
    const hiddenSuitesContainer = document.getElementById('hiddenSuitesContainer');

    checkboxes.forEach(cb => {
    // Add to the displayed list
    const li = document.createElement('li');
    li.textContent = cb.dataset.description;
    selectedSuitesList.appendChild(li);

    // Add hidden input for the suite ID
    const hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = 'suite_ids';
    hidden.value = cb.value;
    hiddenSuitesContainer.appendChild(hidden);

    // Uncheck it so user doesn't accidentally re-add it
    cb.checked = false;
    });
});
}

// Used to solve pagination issue to prevent page reload on page change
document.addEventListener("DOMContentLoaded", function() {
    // Use event delegation to intercept clicks on pagination links within the pagination container.
    const paginationContainer = document.querySelector(".pagination-links");
    if (paginationContainer) {
      paginationContainer.addEventListener("click", function(e) {
        if (e.target.tagName.toLowerCase() === "a") {
          e.preventDefault();
          const url = e.target.getAttribute("href");
  
          // Send an AJAX GET request to the pagination URL.
          fetch(url, {
            headers: {
              "X-Requested-With": "XMLHttpRequest"
            }
          })
          .then(response => response.text())
          .then(html => {
            // Create a temporary DOM element to hold the returned HTML.
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
  
            // Extract the updated suites list and pagination links.
            const newSuitesList = doc.querySelector(".suites-list");
            const newPaginationLinks = doc.querySelector(".pagination-links");
  
            // Update the current page's suites list and pagination links.
            const currentSuitesList = document.querySelector(".suites-list");
            const currentPaginationLinks = document.querySelector(".pagination-links");
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
  });
  