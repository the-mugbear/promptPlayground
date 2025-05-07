/**
 * Script: PayloadTokenEnforcer
 * Purpose: Ensure a required substitution token is present in the HTTP payload
 *          before submitting the form, and provide a button to insert that token
 *          at the current cursor position or replace any selected text.
 */

document.addEventListener("DOMContentLoaded", function() {
  // 1) Grab references to the form and payload textarea
  // try both form IDs
  const form =
    document.getElementById("create-endpoint-form") ||
    document.getElementById("manual-test-form");

  if (!form) {
    // no matching form on this page → do nothing
    return;
  }

  const httpPayloadField = document.getElementById("http_payload");
  //    The token must appear in the payload; injected server‑side via Jinja
  const token = "{{INJECT_PROMPT}}";

  // Helper function to validate token presence
  function validateToken() {
    const value = httpPayloadField.value;
    console.log("Validating payload:", value); // Debug log
    
    // Check if token exists as a complete token (not part of another token)
    const hasToken = value.includes(token);
    
    // Check if token is part of a valid JSON string value
    const isInJsonString = value.includes(`"${token}"`) && 
                          (value.includes(`"content": "${token}"`) || 
                           value.includes(`"prompt": "${token}"`) ||
                           value.includes(`"input": "${token}"`) ||
                           value.includes(`"text": "${token}"`));
    
    console.log("Token found:", hasToken); // Debug log
    console.log("Token is in JSON string:", isInJsonString); // Debug log
    
    if (!hasToken || (value.includes(`"${token}"`) && !isInJsonString)) {
      httpPayloadField.setCustomValidity(
        "Your HTTP Payload must include the token: " + token + 
        "\nNote: The token should be part of a JSON string value (e.g., in a 'content' or 'prompt' field)."
      );
      return false;
    } else {
      httpPayloadField.setCustomValidity("");
      return true;
    }
  }

  // 2) On form submission, validate that the payload contains the token
  form.addEventListener("submit", function(e) {
    console.log("Form submitted, validating token..."); // Debug log
    if (!validateToken()) {
      e.preventDefault();
      httpPayloadField.reportValidity();
    }
  });

  // 3) As the user types, clear the error once they include the token
  httpPayloadField.addEventListener("input", validateToken);

  // 4) Enable an "Insert Token" button to inject the token at cursor/selection
  const insertTokenBtn = document.getElementById("insertTokenBtn");
  if (insertTokenBtn) {
    insertTokenBtn.addEventListener("click", function() {
      const start = httpPayloadField.selectionStart;
      const end = httpPayloadField.selectionEnd;
      const text = httpPayloadField.value;
      const before = text.substring(0, start);
      const after = text.substring(end);
      httpPayloadField.value = before + token + after;
      // Place cursor after the inserted token
      httpPayloadField.selectionStart = httpPayloadField.selectionEnd = start + token.length;
      httpPayloadField.focus();
      // Validate after insertion
      validateToken();
    });
  }

  // 5) Add JSON formatting functionality
  window.formatHttpPayload = function() {
    try {
      const payload = httpPayloadField.value;
      if (!payload.trim()) {
        alert("Please enter some JSON to format");
        return;
      }
      
      // Try to parse and format the JSON
      const parsed = JSON.parse(payload);
      const formatted = JSON.stringify(parsed, null, 2);
      httpPayloadField.value = formatted;
      
      // Validate token after formatting
      validateToken();
    } catch (e) {
      alert("Invalid JSON: " + e.message);
    }
  };
});
