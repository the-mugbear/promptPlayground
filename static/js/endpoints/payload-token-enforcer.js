/**
 * Script: PayloadTokenEnforcer
 * Purpose: Ensure a required substitution token is present in the HTTP payload
 * before submitting the form, and provide buttons to insert different
 * versions of that token.
 */

document.addEventListener("DOMContentLoaded", function () {
  // 1) Grab references to the form and payload textarea
  const form =
    document.getElementById("create-endpoint-form") ||
    document.getElementById("manual-test-form");

  if (!form) {
    // No matching form on this page, do nothing
    return;
  }

  const httpPayloadField = document.getElementById("http_payload");
  const baseToken = "{{INJECT_PROMPT}}";
  const jsonToken = "{{ INJECT_PROMPT | tojson }}";

  // --- Main Validation Function ---
  function validateToken() {
    const value = httpPayloadField.value;

    // --- UPDATED VALIDATION LOGIC ---
    // Use a regular expression to check for either token permutation.
    // This looks for "{{INJECT_PROMPT}}" with an optional "| tojson" filter inside.
    const tokenRegex = /\{\{\s*INJECT_PROMPT\s*(?:\|\s*tojson\s*)?\}\}/;
    const hasToken = tokenRegex.test(value);

    if (!hasToken) {
      httpPayloadField.setCustomValidity(
        "Your HTTP Payload must include a valid prompt token, e.g., {{INJECT_PROMPT}} or {{INJECT_PROMPT | tojson}}."
      );
      return false; // Block submission if no valid token is found
    }

    // Clear any previous error message if a valid token is present.
    httpPayloadField.setCustomValidity("");
    return true;
  }
  // --- END OF UPDATED LOGIC ---

  // --- Event Listeners ---
  form.addEventListener("submit", function (e) {
    if (!validateToken()) {
      e.preventDefault();
      httpPayloadField.reportValidity();
    }
  });

  httpPayloadField.addEventListener("input", validateToken);


  // --- Button Handlers ---

  // Helper function to insert text at the cursor
  function insertTextAtCursor(textToInsert) {
    const start = httpPayloadField.selectionStart;
    const end = httpPayloadField.selectionEnd;
    const text = httpPayloadField.value;
    const before = text.substring(0, start);
    const after = text.substring(end);

    httpPayloadField.value = before + textToInsert + after;

    // Place cursor after the inserted text
    httpPayloadField.selectionStart = httpPayloadField.selectionEnd = start + textToInsert.length;
    httpPayloadField.focus();
    validateToken(); // Re-validate after insertion
  }

  // Listener for the basic token button
  const insertTokenBtn = document.getElementById("insertTokenBtn");
  if (insertTokenBtn) {
    insertTokenBtn.addEventListener("click", function () {
      insertTextAtCursor(baseToken);
    });
  }

  // Listener for the JSON-safe token button
  const insertJsonTokenBtn = document.getElementById("insertJsonTokenBtn");
  if (insertJsonTokenBtn) {
    insertJsonTokenBtn.addEventListener("click", function (e) {
      e.preventDefault(); // This is a link in a dropdown, so prevent default action
      insertTextAtCursor(jsonToken);
    });
  }

  // --- JSON Formatting Functionality ---
  window.formatHttpPayload = function () {
    const payload = httpPayloadField.value;
    if (!payload.trim()) {
      alert("Please enter some JSON to format");
      return;
    }
    try {
      // Temporarily replace placeholders to allow formatting
      const placeholder = '"__TEMP_PROMPT_PLACEHOLDER__"';
      const tempPayload = payload.replace(/\{\{\s*INJECT_PROMPT\s*(\|\s*tojson\s*)?\}\}/g, placeholder);

      const parsed = JSON.parse(tempPayload);
      let formatted = JSON.stringify(parsed, null, 2);

      // Restore the original placeholder that was used
      const originalPlaceholder = payload.includes(jsonToken) ? jsonToken : baseToken;
      formatted = formatted.replace(placeholder, originalPlaceholder);

      httpPayloadField.value = formatted;
      validateToken();
    } catch (e) {
      alert("Invalid JSON structure: " + e.message);
    }
  };
});