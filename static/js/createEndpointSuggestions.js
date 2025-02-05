let lastFocusedField = null;
let SUGGESTIONS = null;  // We'll store fetched data once

document.addEventListener("DOMContentLoaded", function() {
  // references to fields
  const hostnameField = document.getElementById("hostname");
  const endpointField = document.getElementById("endpoint");
  const payloadField = document.getElementById("http_payload");

  // attach focus listeners
  hostnameField.addEventListener("focus", () => {
    lastFocusedField = hostnameField;             // ← STORE the reference
    fetchAndShowSuggestions("hostnames");
  });
  endpointField.addEventListener("focus", () => {
    lastFocusedField = endpointField;             // ← STORE the reference
    fetchAndShowSuggestions("paths");
  });
  payloadField.addEventListener("focus", () => {
    lastFocusedField = payloadField;              // ← STORE the reference
    fetchAndShowSuggestions("payloads");
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
    li.textContent = item;
    // On click, copy this item to whichever field was last focused
    li.addEventListener("click", () => {
      copySuggestionToFocusedField(item);
    });
    listEl.appendChild(li);
  });
}

function copySuggestionToFocusedField(value) {
  if (lastFocusedField) {
    lastFocusedField.value = value;
  }
}
