// This is responsible for providing the preview pane functionality when selecting transformations

document.addEventListener("DOMContentLoaded", function() {
    const formEl = document.getElementById("create-case-form") || document.getElementById("create-suite-form");
    // Use data-preview-url attribute to determine the AJAX endpoint.
    const previewUrl = formEl.getAttribute("data-preview-url") || "/test_suites/preview_transform";
  
    const newTestCasesEl = document.getElementById("new_test_cases");
    const previewArea = document.getElementById("preview-area");
  
    const transformationCheckboxes = document.querySelectorAll(
      'input[type="checkbox"][name="transformations"]'
    );
    const orderedTransformationsInput = document.getElementById("ordered_transformations");
    const transformationQueueEl = document.getElementById("transformation-queue");
  
    const prependTextEl = document.querySelector('input[name="text_to_prepend"]');
    const postpendTextEl = document.querySelector('input[name="text_to_postpend"]');
  
    let transformationQueue = [];
  
    function debounce(func, wait) {
      let timeout;
      return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
      };
    }
  
    const debouncedUpdatePreview = debounce(updatePreview, 300);
  
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
  
    newTestCasesEl.addEventListener("input", debouncedUpdatePreview);
    prependTextEl.addEventListener("input", debouncedUpdatePreview);
    postpendTextEl.addEventListener("input", debouncedUpdatePreview);
  
    const previewBtn = document.getElementById("preview-button");
    if (previewBtn) {
      previewBtn.addEventListener("click", debouncedUpdatePreview);
    }
  
    function updateTransformationQueueDisplay() {
      transformationQueueEl.innerHTML = "";
      transformationQueue.forEach((transform, index) => {
        const li = document.createElement("li");
        li.textContent = `${index + 1}. ${transform}`;
        transformationQueueEl.appendChild(li);
      });
      orderedTransformationsInput.value = JSON.stringify(transformationQueue);
    }
  
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
  
      fetch(previewUrl, {
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
  
    updatePreview();
  });
  