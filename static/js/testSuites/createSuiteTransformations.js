document.addEventListener("DOMContentLoaded", function() {
  const newTestCasesEl = document.getElementById("new_test_cases");
  const previewArea = document.getElementById("preview-area");

  // Transformation checkboxes and related elements
  const transformationCheckboxes = document.querySelectorAll(
    'input[type="checkbox"][name="transformations"]'
  );
  const orderedTransformationsInput = document.getElementById("ordered_transformations");
  const transformationQueueEl = document.getElementById("transformation-queue");

  // Parameter fields for transformations
  const prependTextEl = document.querySelector('input[name="text_to_prepend"]');
  const postpendTextEl = document.querySelector('input[name="text_to_postpend"]');

  // Array to store the order of transformations
  let transformationQueue = [];

  // Debounce helper: delays function execution until after 'wait' milliseconds have elapsed
  function debounce(func, wait) {
    let timeout;
    return function(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // Wrap updatePreview with a debounce delay of 300ms
  const debouncedUpdatePreview = debounce(updatePreview, 300);

  // Add event listeners to each transformation checkbox
  transformationCheckboxes.forEach(cb => {
    cb.addEventListener("change", function() {
      const value = cb.value;
      if (cb.checked) {
        if (!transformationQueue.includes(value)) {
          transformationQueue.push(value);
        }
      } else {
        transformationQueue = transformationQueue.filter(val => val !== value);
      }
      updateTransformationQueueDisplay();
      debouncedUpdatePreview();
    });
  });

  // Listen for changes in the new test cases textarea and parameter fields
  newTestCasesEl.addEventListener("input", debouncedUpdatePreview);
  prependTextEl.addEventListener("input", debouncedUpdatePreview);
  postpendTextEl.addEventListener("input", debouncedUpdatePreview);

  // Optional: manual preview button (if present)
  const previewBtn = document.getElementById("preview-button");
  if (previewBtn) {
    previewBtn.addEventListener("click", debouncedUpdatePreview);
  }

  // Update the visible transformation queue and hidden input
  function updateTransformationQueueDisplay() {
    transformationQueueEl.innerHTML = "";
    transformationQueue.forEach((transform, index) => {
      const li = document.createElement("li");
      li.textContent = `${index + 1}. ${transform}`;
      transformationQueueEl.appendChild(li);
    });
    orderedTransformationsInput.value = JSON.stringify(transformationQueue);
  }

  // Collect data and send preview request
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
