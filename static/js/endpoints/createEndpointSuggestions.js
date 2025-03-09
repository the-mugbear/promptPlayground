// This script used to fetch and provide suggestions when the user selects a form field
// values are fetched from the database and only exist in the database after an entry is registered in the database

let lastFocusedField = null;
let SUGGESTIONS = null;  // We'll store fetched data once

document.addEventListener("DOMContentLoaded", function() {
  // references to fields
  const hostnameField = document.getElementById("hostname");
  const endpointField = document.getElementById("endpoint");
  const payloadField = document.getElementById("http_payload");
  const rawPayloads = document.getElementById("raw_headers");
  const previewDiv = document.getElementById("suggestionText");

  // attach focus listeners
  hostnameField.addEventListener("focus", () => {
    lastFocusedField = hostnameField;             // ← STORE the reference
    previewDiv.textContent = '';
    fetchAndShowSuggestions("hostnames");
  });
  endpointField.addEventListener("focus", () => {
    lastFocusedField = endpointField;             // ← STORE the reference
    previewDiv.textContent = '';
    fetchAndShowSuggestions("paths");
  });
  payloadField.addEventListener("focus", () => {
    lastFocusedField = payloadField;              // ← STORE the reference
    previewDiv.textContent = 'Previous entries suggested below. Format JSON attempts to pretty print JSON text if formatted correctly';
    fetchAndShowSuggestions("payloads");
  });
  rawPayloads.addEventListener("focus", function() {
    // console.log("Focused raw_payloads");
    lastFocusedField = rawPayloads;  
    previewDiv.textContent = 'Modify and remove key/value pairs below before creating endpoint';
  });
});

/** 
 * We'll fetch once from the server and store in SUGGESTIONS
 * so we don't do repeated requests each time 
*/
function fetchAndShowSuggestions(key) {
  if (!SUGGESTIONS) {
    fetch('/endpoints/get_suggestions')
      .then(response => response.json())
      .then(data => {
        SUGGESTIONS = data; // e.g. { hostnames: [...], paths: [...], payloads: [...] }
        populateSuggestionList(SUGGESTIONS[key] || []);
      })
      .catch(err => console.error("Error fetching suggestions:", err));
  } else {
    populateSuggestionList(SUGGESTIONS[key] || []);
  }
}

function populateSuggestionList(items) {
  const listEl = document.getElementById("suggestion-list");
  listEl.innerHTML = "";
  items.forEach(item => {
    const li = document.createElement("li");

    // Attempt to pretty-print the JSON if possible
    let displayText = item;
    try {
      const parsed = JSON.parse(item);
      // Use pretty-print without extra whitespace if too long
      displayText = JSON.stringify(parsed, null, 2);
    } catch (e) {
      // Not JSON, so leave it as is
    }
    
    // Set a maximum length for the display text
    const maxLength = 100;
    if (displayText.length > maxLength) {
      li.textContent = displayText.substring(0, maxLength) + '...';
      li.title = displayText; // Show full content on hover as a tooltip
    } else {
      li.textContent = displayText;
    }

    // When clicked, copy the full suggestion (not the truncated version) to the focused field
    li.addEventListener("click", () => {
      copySuggestionToFocusedField(item);
    });
    listEl.appendChild(li);
  });
}


function copySuggestionToFocusedField(value) {
  if (lastFocusedField) {
    lastFocusedField.value = value;

    // Fire an 'input' event so the duplication script sees it
    lastFocusedField.dispatchEvent(new Event('input', { bubbles: true }));
  }
}
