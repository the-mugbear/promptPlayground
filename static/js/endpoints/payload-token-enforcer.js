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

  // 2) On form submission, validate that the payload contains the token
  form.addEventListener("submit", function(e) {
    if (!httpPayloadField.value.includes(token)) {
      // If missing, stop submission and show an error on the textarea
      e.preventDefault();
      httpPayloadField.setCustomValidity(
        "Your HTTP Payload must include the token: " + token
      );
      httpPayloadField.reportValidity();
    } else {
      // If present, clear any previous custom error
      httpPayloadField.setCustomValidity("");
    }
  });

  // 3) As the user types, clear the error once they include the token
  httpPayloadField.addEventListener("input", function() {
    if (this.value.includes(token)) {
      this.setCustomValidity("");
    }
  });

  // 4) Enable an “Insert Token” button to inject the token at cursor/selection
  const insertTokenBtn = document.getElementById("insertTokenBtn");
  if (insertTokenBtn) {
    insertTokenBtn.addEventListener("click", function() {
      // Remember current selection/cursor positions
      const start = httpPayloadField.selectionStart;
      const end   = httpPayloadField.selectionEnd;

      // Replace selected text (or insert at cursor) with the token
      httpPayloadField.value =
        httpPayloadField.value.substring(0, start) +
        token +
        httpPayloadField.value.substring(end);

      // Move cursor to immediately after the inserted token
      httpPayloadField.selectionStart =
      httpPayloadField.selectionEnd   = start + token.length;

      // Return focus to the payload textarea
      httpPayloadField.focus();
    });
  }
});
