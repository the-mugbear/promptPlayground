// static/js/createSuiteTransformations.js

document.addEventListener("DOMContentLoaded", function() {
  const newTestCasesEl = document.getElementById("new_test_cases");
  const previewArea = document.getElementById("preview-area");

  // Gather references to the transformation checkboxes
  const transformationCheckboxes = document.querySelectorAll(
    'input[type="checkbox"][name="transformations"]'
  );

  // Hidden input to store the ordered transformations
  const orderedTransformationsInput = document.getElementById("ordered_transformations");
  // Element for displaying the transformation order queue
  const transformationQueueEl = document.getElementById("transformation-queue");

  // Prepend/Postpend text fields
  const prependTextEl = document.querySelector('input[name="text_to_prepend"]');
  const postpendTextEl = document.querySelector('input[name="text_to_postpend"]');

  // Array to store the order of transformations as they are selected
  let transformationQueue = [];

  // Add event listeners to each transformation checkbox
  transformationCheckboxes.forEach(cb => {
    cb.addEventListener("change", function() {
      const value = cb.value;
      if (cb.checked) {
        // Add transformation at the end if not already in the queue
        if (!transformationQueue.includes(value)) {
          transformationQueue.push(value);
        }
      } else {
        // Remove transformation from the queue when unchecked
        transformationQueue = transformationQueue.filter(val => val !== value);
      }
      updateTransformationQueueDisplay();
      updatePreview();
    });
  });

  // Listen for changes in the new test cases textarea and the parameter fields
  newTestCasesEl.addEventListener("input", updatePreview);
  prependTextEl.addEventListener("input", updatePreview);
  postpendTextEl.addEventListener("input", updatePreview);

  // Optionally, if you want to keep a manual preview button:
  const previewBtn = document.getElementById("preview-button");
  if (previewBtn) {
    previewBtn.addEventListener("click", updatePreview);
  }

  // Updates the visible transformation queue and hidden input value.
  function updateTransformationQueueDisplay() {
    transformationQueueEl.innerHTML = "";
    transformationQueue.forEach((transform, index) => {
      const li = document.createElement("li");
      li.textContent = `${index + 1}. ${transform}`;
      transformationQueueEl.appendChild(li);
    });
    orderedTransformationsInput.value = JSON.stringify(transformationQueue);
  }

  // Collects data from the form and sends a preview request.
  function updatePreview() {
    const lines = newTestCasesEl.value
      .split("\n")
      .map(line => line.trim())
      .filter(Boolean);

    const selectedTransforms = transformationQueue.slice();

    const params = {
      text_to_prepend: prependTextEl.value,
      text_to_postpend: postpendTextEl.value
    };

    // If no test case lines are provided, clear the preview.
    if (lines.length === 0) {
      previewArea.value = "";
      return;
    }

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
  }

  // Initial preview update in case the form is pre-filled.
  updatePreview();
});
