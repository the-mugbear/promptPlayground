/**
 * Script Name: FieldSuggestionHelper
 * Purpose: When the user focuses a form field, fetch and display past database entries
 *          as suggestions, allowing easy reuse of hostnames, paths, payloads, etc.
 * Usage: Include this script on pages containing:
 *   • Inputs with IDs “hostname”, “endpoint”, “http_payload”, “raw_headers”
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

  // When each field gains focus, record it and update helper text & suggestions
  hostnameField.addEventListener("focus", () => {
    lastFocusedField = hostnameField;
    previewDiv.textContent = '';
    fetchAndShowSuggestions("hostnames");
  });

  endpointField.addEventListener("focus", () => {
    lastFocusedField = endpointField;
    previewDiv.textContent = '';
    fetchAndShowSuggestions("paths");
  });

  payloadField.addEventListener("focus", () => {
    lastFocusedField = payloadField;
    previewDiv.textContent = 'Previous entries suggested below. JSON will be pretty‑printed if valid.';
    fetchAndShowSuggestions("payloads");
  });

  rawHeaders.addEventListener("focus", () => {
    lastFocusedField = rawHeaders;
    previewDiv.textContent = 'Modify or remove key/value pairs below before creating endpoint.';
    // No fetch here — suggestions only for hostname, endpoint, payload
  });
});

/**
 * Fetches the suggestion map from the server once, then delegates to populateSuggestionList.
 * key should be one of the object’s properties: "hostnames", "paths", or "payloads".
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
 * Inserts the chosen suggestion into the lastFocusedField and
 * fires an input event so any sync scripts pick up the change.
 */
function copySuggestionToFocusedField(value) {
  if (!lastFocusedField) return;
  lastFocusedField.value = value;
  lastFocusedField.dispatchEvent(new Event('input', { bubbles: true }));
}
