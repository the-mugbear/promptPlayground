// static/js/createSuiteTransformations.js

document.addEventListener("DOMContentLoaded", function() {
    const previewBtn = document.getElementById("preview-button");
    const newTestCasesEl = document.getElementById("new_test_cases");
    const previewArea = document.getElementById("preview-area");
  
    // Gather references to the transformation checkboxes
    const transformationCheckboxes = document.querySelectorAll(
      'input[type="checkbox"][name="transformations"]'
    );
  
    // Prepend/Postpend text fields
    const prependTextEl = document.querySelector('input[name="text_to_prepend"]');
    const postpendTextEl = document.querySelector('input[name="text_to_postpend"]');
  
    previewBtn.addEventListener("click", function() {
      // 1) Collect the lines from the textarea
      const lines = newTestCasesEl.value
        .split("\n")
        .map(line => line.trim())
        .filter(Boolean);
  
      // 2) Gather user-selected transforms
      const selectedTransforms = [];
      transformationCheckboxes.forEach(cb => {
        if (cb.checked) {
          selectedTransforms.push(cb.value);
        }
      });
  
      // 3) Collect the user’s typed param values
      const params = {
        text_to_prepend: prependTextEl.value,
        text_to_postpend: postpendTextEl.value
      };
  
      // 4) Make an AJAX call to the server
      fetch("/test_suites/preview_transform", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lines: lines,
          transformations: selectedTransforms,
          params: params
        })
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        // 5) Fill the preview textarea
        if (data.transformed_lines) {
          previewArea.value = data.transformed_lines.join("\n");
        } else {
          previewArea.value = "No lines returned in response.";
        }
      })
      .catch(err => {
        console.error("Preview error:", err);
        previewArea.value = `Error: ${err.message}`;
      });
    });
  });
  