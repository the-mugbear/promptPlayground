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
    
    if (!hasToken) {
      httpPayloadField.setCustomValidity(
        "Your HTTP Payload must include the token: " + token
      );
      return false;
    }

    // If the token is between quotes, it must be part of a valid JSON field
    if (value.includes(`"${token}"`) || value.includes(`'${token}'`)) {
      try {
        // Try to parse as JSON to validate structure
        const jsonObj = JSON.parse(value);
        
        // Recursively search for the token in JSON values
        function findTokenInObject(obj) {
          for (const key in obj) {
            const val = obj[key];
            if (typeof val === 'string' && val.includes(token)) {
              return true;
            } else if (typeof val === 'object' && val !== null) {
              if (findTokenInObject(val)) return true;
            }
          }
          return false;
        }
        
        if (!findTokenInObject(jsonObj)) {
          httpPayloadField.setCustomValidity(
            "The token must be part of a valid JSON string value field"
          );
          return false;
        }
      } catch (e) {
        httpPayloadField.setCustomValidity(
          "Invalid JSON format: " + e.message
        );
        return false;
      }
    }
    
    httpPayloadField.setCustomValidity("");
    return true;
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
