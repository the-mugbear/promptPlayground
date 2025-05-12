/**
 * Script Name: FieldSuggestionHelper
 * Purpose: When the user focuses a form field, fetch and display past database entries
 *          as suggestions, allowing easy reuse of hostnames, paths, payloads, etc.
 * Usage: Include this script on pages containing:
 *   • Inputs with IDs "hostname", "endpoint", "http_payload", "raw_headers"
 *   • A <div id="suggestionText"> for explanatory text
 *   • A <ul id="suggestion-list"> to hold suggestion items
 */

let lastFocusedField = null;  // Tracks which input was last focused
let SUGGESTIONS = null;       // Cache for fetched suggestion data

document.addEventListener("DOMContentLoaded", function() {
  // Grab references to the visible inputs
  const hostnameField = document.getElementById("hostname");
  const endpointField = document.getElementById("endpoint");
  const payloadField  = document.getElementById("http_payload");
  const rawHeaders    = document.getElementById("raw_headers");
  const previewDiv    = document.getElementById("suggestionText");

  // Function to safely clear suggestion list
  function clearSuggestionList() {
    const suggestionList = document.getElementById("suggestion-list");
    if (suggestionList) {
      suggestionList.innerHTML = '';
    }
  }

  // When each field gains focus, record it and update helper text & suggestions
  hostnameField?.addEventListener("focus", () => {
    lastFocusedField = hostnameField;
    if (previewDiv) previewDiv.textContent = '';
    clearSuggestionList();
    fetchAndShowSuggestions("hostnames");
  });

  endpointField?.addEventListener("focus", () => {
    lastFocusedField = endpointField;
    if (previewDiv) previewDiv.textContent = '';
    clearSuggestionList();
    fetchAndShowSuggestions("paths");
  });

  payloadField?.addEventListener("focus", () => {
    lastFocusedField = payloadField;
    if (previewDiv) previewDiv.textContent = 'Previous entries suggested below. JSON will be pretty‑printed if valid.';
    clearSuggestionList();
    fetchAndShowSuggestions("payloads");
  });

  rawHeaders?.addEventListener("focus", () => {
    lastFocusedField = rawHeaders;
    if (previewDiv) previewDiv.textContent = 'Modify or remove key/value pairs below before creating endpoint.';
    clearSuggestionList();
    // No fetch here — suggestions only for hostname, endpoint, payload
  });
});

/**
 * Fetches the suggestion map from the server once, then delegates to populateSuggestionList.
 * key should be one of the object's properties: "hostnames", "paths", or "payloads".
 */
function fetchAndShowSuggestions(key) {
  if (!SUGGESTIONS) {
    fetch('/endpoints/get_suggestions')
      .then(res => res.json())
      .then(data => {
        SUGGESTIONS = data;  // e.g. { hostnames: [...], paths: [...], payloads: [...] }
        populateSuggestionList(SUGGESTIONS[key] || []);
      })
      .catch(err => console.error("Error fetching suggestions:", err));
  } else {
    // Already have data; just refresh the list for this key
    populateSuggestionList(SUGGESTIONS[key] || []);
  }
}

/**
 * Renders an array of string items into the <ul id="suggestion-list">.
 * Truncates long entries and pretty‑prints valid JSON.
 */
function populateSuggestionList(items) {
  const listEl = document.getElementById("suggestion-list");
  if (!listEl) return;
  
  listEl.innerHTML = "";

  items.forEach(item => {
    const li = document.createElement("li");
    let displayText = item;

    // Try to pretty-print JSON strings
    try {
      const parsed = JSON.parse(item);
      displayText = JSON.stringify(parsed, null, 2);
    } catch (e) {
      // Not JSON — leave displayText as the raw string
    }

    // Truncate for readability, with tooltip for full text
    const maxLength = 100;
    if (displayText.length > maxLength) {
      li.textContent = displayText.slice(0, maxLength) + '…';
      li.title = displayText;
    } else {
      li.textContent = displayText;
    }

    // On click, copy the full original item (not truncated) into the focused field
    li.addEventListener("click", () => copySuggestionToFocusedField(item));
    listEl.appendChild(li);
  });
}

/**
 * Copies a suggestion into the currently focused field.
 */
function copySuggestionToFocusedField(text) {
  if (!lastFocusedField) return;
  lastFocusedField.value = text;
  lastFocusedField.dispatchEvent(new Event('input')); // Trigger any input listeners
}
