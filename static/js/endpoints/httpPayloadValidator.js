// Allows token to be injected via JS as well as ensures the HTTP Payload contains
// the substitution token before form submission
document.addEventListener("DOMContentLoaded", function() {
    const form = document.getElementById("create-endpoint-form");
    const httpPayloadField = document.getElementById("http_payload");
    const token = "{{INJECT_PROMPT}}";
    
    // Validate on form submission: prevent form submission if token is missing.
    form.addEventListener("submit", function(e) {
      if (!httpPayloadField.value.includes(token)) {
        e.preventDefault();
        httpPayloadField.setCustomValidity("Your HTTP Payload must include the token: " + token);
        httpPayloadField.reportValidity();
      } else {
        httpPayloadField.setCustomValidity("");
      }
    });
    
    // Clear custom validity when the token is present.
    httpPayloadField.addEventListener("input", function() {
      if (this.value.includes(token)) {
        this.setCustomValidity("");
      }
    });
    
    // Insert the token into the HTTP Payload field by replacing highlighted text.
    const insertTokenBtn = document.getElementById("insertTokenBtn");
    if (insertTokenBtn) {
      insertTokenBtn.addEventListener("click", function() {
        const start = httpPayloadField.selectionStart;
        const end = httpPayloadField.selectionEnd;
        // Replace the selected text (or insert at the cursor if no text is selected).
        httpPayloadField.value = httpPayloadField.value.substring(0, start) +
                                  token +
                                  httpPayloadField.value.substring(end);
        // Move the cursor to just after the inserted token.
        httpPayloadField.selectionStart = httpPayloadField.selectionEnd = start + token.length;
        // Return focus to the textarea.
        httpPayloadField.focus();
      });
    }
  });
  