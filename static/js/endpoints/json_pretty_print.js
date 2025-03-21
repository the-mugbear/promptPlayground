// Used to help format HTTP payloads copied from dev tools
function formatHttpPayload() {
    const textArea = document.getElementById('http_payload');
    const raw = textArea.value.trim();

    if (!raw) {
      return; // If empty, do nothing
    }

    try {
      // Attempt to parse as JSON
      const parsed = JSON.parse(raw);
      // If successful, pretty-print with 2-space indentation
      textArea.value = JSON.stringify(parsed, null, 2);
    } catch (error) {
      // If parse fails, optionally show error or do nothing
      console.error("Invalid JSON, cannot format:", error);
      alert("Invalid JSON. Please correct any errors before formatting.");
    }
  }