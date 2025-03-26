// findReplace.js
document.addEventListener("DOMContentLoaded", function() {
    function findReplacePayload() {
      const payloadTextarea = document.getElementById('endpointPayload');
      if (!payloadTextarea.value.trim()) {
        alert("No payload to edit.");
        return;
      }
      const findStr = prompt("Find:");
      if (!findStr) return;
      const replaceStr = prompt("Replace with:");
      if (replaceStr === null) return; // User clicked cancel
      payloadTextarea.value = payloadTextarea.value.split(findStr).join(replaceStr);
    }
  
    function findReplaceHeaders() {
      const headerKeys = document.querySelectorAll('.header-key');
      const headerValues = document.querySelectorAll('.header-value');
      if (!headerKeys.length) {
        alert("No headers to edit.");
        return;
      }
      const findStr = prompt("Find:");
      if (!findStr) return;
      const replaceStr = prompt("Replace with:");
      if (replaceStr === null) return;
      headerKeys.forEach(input => {
        input.value = input.value.split(findStr).join(replaceStr);
      });
      headerValues.forEach(input => {
        input.value = input.value.split(findStr).join(replaceStr);
      });
    }
  
    // Expose functions globally so they can be called from elsewhere if needed
    window.findReplacePayload = findReplacePayload;
    window.findReplaceHeaders = findReplaceHeaders;
  });
  