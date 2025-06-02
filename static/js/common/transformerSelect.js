// static/js/common/transformerSelect.js

document.addEventListener('DOMContentLoaded', () => {
  // 1) Grab all the checkbox inputs with name="transformations"
  const transformCheckboxes = Array.from(
    document.querySelectorAll('input[name="transformations"]')
  );
  if (transformCheckboxes.length === 0) {
    // No transform‐checkboxes on this page ─ nothing to do
    return;
  }

  // 2) Grab the hidden input that holds our JSON‐encoded order list
  const orderedTransformsInput = document.getElementById('ordered_transformations');
  // (should exist immediately under the same <form> as your checkboxes)
  if (!orderedTransformsInput) {
    console.warn('No #ordered_transformations hidden input found.');
    return;
  }

  // 3) Array to hold the exact order the user checks boxes
  let selectionOrder = [];

  // 4) On page load, pre‐populate if any checkboxes are already checked
  transformCheckboxes.forEach(cb => {
    if (cb.checked) {
      selectionOrder.push(cb.value);
    }
  });
  orderedTransformsInput.value = JSON.stringify(selectionOrder);

  // 5) Whenever a checkbox toggles, update selectionOrder and the hidden field
  transformCheckboxes.forEach(cb => {
    cb.addEventListener('change', () => {
      const val = cb.value;
      if (cb.checked) {
        if (!selectionOrder.includes(val)) {
          selectionOrder.push(val);
        }
      } else {
        selectionOrder = selectionOrder.filter(name => name !== val);
      }
      orderedTransformsInput.value = JSON.stringify(selectionOrder);

      // (Optional) Update the <ol id="selectedTransformsOrder"> display if you want a user‐facing list
      const previewList = document.getElementById('selectedTransformsOrder');
      if (previewList) {
        // Clear and re‐populate
        previewList.innerHTML = '';
        selectionOrder.forEach(name => {
          const li = document.createElement('li');
          li.textContent = name;
          previewList.appendChild(li);
        });
      }
    });
  });

  // 6) Just before <form> submits, ensure selectionOrder matches all checked boxes
  const createRunForm = document.getElementById('createRunForm');
  if (createRunForm) {
    createRunForm.addEventListener('submit', () => {
      // Defensive recheck: in case someone toggled an input via DevTools
      selectionOrder = transformCheckboxes
        .filter(cb => cb.checked)
        .map(cb => cb.value);
      orderedTransformsInput.value = JSON.stringify(selectionOrder);
    });
  }
});
