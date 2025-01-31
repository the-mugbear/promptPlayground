// We'll store the last field that was focused.
let lastFocusedField = null;

document.addEventListener("DOMContentLoaded", function() {
  // Grab references to form fields on the left
  const hostnameField = document.getElementById("hostname");
  const endpointField = document.getElementById("endpoint");
  const payloadField = document.getElementById("http_payload");
  const headersField = document.getElementById("raw_headers");

  // Add focus listeners to each
  hostnameField.addEventListener("focus", () => onFieldFocus("hostname", hostnameField));
  endpointField.addEventListener("focus", () => onFieldFocus("endpoint", endpointField));
  payloadField.addEventListener("focus", () => onFieldFocus("http_payload", payloadField));
  headersField.addEventListener("focus", () => onFieldFocus("raw_headers", headersField));
});

function onFieldFocus(fieldId, fieldElement) {
  // Store which field is focused
  lastFocusedField = fieldElement;
  // Get suggestions for this field ID
  const suggestions = SUGGESTION_DATA[fieldId] || [];
  populateSuggestions(suggestions);
}

// Example local suggestion data
const SUGGESTION_DATA = {
  "hostname": [
    "https://api.example.com",
    "https://api.myservice.org",
    "http://localhost:5000"
  ],
  "endpoint": [
    "/v1/submit",
    "/v2/analyze",
    "/v1/data"
  ],
  "http_payload": [
    "{\"example\": \"payload1\"}",
    "{\"another\": \"payload2\"}"
  ],
  "raw_headers": [
    "Content-Type: application/json\nAuthorization: Bearer <token>",
    "X-Custom-Header: 123\nUser-Agent: MyTestClient"
  ]
};

function populateSuggestions(suggestions) {
  const suggestionList = document.getElementById("suggestion-list");
  suggestionList.innerHTML = ""; // Clear old suggestions

  suggestions.forEach(item => {
    const li = document.createElement("li");
    li.textContent = item;
    li.addEventListener("click", () => {
      copySuggestionToLastFocused(item);
    });
    suggestionList.appendChild(li);
  });
}

function copySuggestionToLastFocused(value) {
  // If we have a stored reference to the last focused field, fill it
  if (lastFocusedField) {
    lastFocusedField.value = value;
  }
}
