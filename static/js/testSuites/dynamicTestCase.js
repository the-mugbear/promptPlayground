document.addEventListener("DOMContentLoaded", function() {
  // Declare testCases in a scope accessible to all handlers.
  let testCases = [];

  // Helper function to collect transformation data from a given container.
  function collectTransformationsFromUI(container) {
    const transformations = [];
    // Find all checkboxes in the container (they all have the same name "transformations")
    const checkboxes = container.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
      if (checkbox.checked) {
        // Use the checkbox's value as the transformation type.
        let transform = { type: checkbox.value };
        // For transformations that require an associated text (e.g., prepend_text, postpend_text),
        // look for the sibling text input within the same parent container (".transform-option").
        if (checkbox.value === "prepend_text" || checkbox.value === "postpend_text") {
          const optionContainer = checkbox.closest('.transform-option');
          if (optionContainer) {
            const textInput = optionContainer.querySelector('input[type="text"]');
            if (textInput && textInput.value.trim() !== "") {
              transform.value = textInput.value.trim();
            }
          }
        }
        transformations.push(transform);
      }
    });
    return transformations;
  }

  // Helper to render transformation order for a test case card.
  function renderTransformationOrder(card, testCase) {
    const orderContainer = card.querySelector('.transformation-order');
    orderContainer.innerHTML = ''; // Clear existing content

    if (testCase.inheritSuiteTransformations) {
      orderContainer.textContent = 'Using suite-level transformations.';
    } else {
      // Check if there are any custom transformations.
      if (!testCase.transformations || testCase.transformations.length === 0) {
        orderContainer.textContent = 'No custom transformations set.';
        return;
      }
      // Create an ordered list showing the transformation order.
      const ol = document.createElement('ol');
      testCase.transformations.forEach(t => {
        const li = document.createElement('li');
        li.textContent = t.type + (t.value ? ` (Parameter: ${t.value})` : '');
        ol.appendChild(li);
      });
      orderContainer.appendChild(ol);
    }
  }

  // Update test case data from the UI in a given card.
  function updateTestCaseData(testCase, card) {
    if (!testCase.inheritSuiteTransformations) {
      const perCaseDiv = card.querySelector('.per-case-transformations');
      // Collect the custom transformations from the UI.
      testCase.transformations = collectTransformationsFromUI(perCaseDiv);
    } else {
      // If inheriting suite-level transformations, clear any custom ones.
      testCase.transformations = [];
    }
    document.getElementById('test_cases_data').value = JSON.stringify(testCases);
  }

  // Toggle display of per-test-case transformation controls.
  function toggleTransformationsSection(card, useSuiteLevel) {
    const perCaseDiv = card.querySelector('.per-case-transformations');
    perCaseDiv.style.display = useSuiteLevel ? 'none' : 'block';
  }

  // Render the dynamic test case cards.
  function renderTestCases() {
    const container = document.getElementById('testCasesContainer');
    container.innerHTML = '';
    testCases.forEach((tc, index) => {
      const card = document.createElement('div');
      card.className = 'test-case-card';
      card.setAttribute('data-index', index);

      // Prompt input
      const promptInput = document.createElement('input');
      promptInput.type = 'text';
      promptInput.placeholder = 'Enter test case prompt';
      promptInput.value = tc.prompt || '';
      promptInput.oninput = e => { tc.prompt = e.target.value; };
      card.appendChild(promptInput);

      // Checkbox for inheriting suite-level transformations
      const inheritLabel = document.createElement('label');
      inheritLabel.textContent = ' Use suite-level transformations';
      const inheritCheckbox = document.createElement('input');
      inheritCheckbox.type = 'checkbox';
      // Default to true unless explicitly set false.
      inheritCheckbox.checked = tc.inheritSuiteTransformations !== false;
      inheritCheckbox.onchange = e => { 
        tc.inheritSuiteTransformations = e.target.checked; 
        toggleTransformationsSection(card, e.target.checked);
        updateTestCaseData(tc, card);
        renderTransformationOrder(card, tc);
      };
      inheritLabel.insertBefore(inheritCheckbox, inheritLabel.firstChild);
      card.appendChild(inheritLabel);

      // Container for per-test-case transformations (clone the hidden template)
      const perCaseDiv = document.createElement('div');
      perCaseDiv.className = 'per-case-transformations';
      perCaseDiv.style.display = inheritCheckbox.checked ? 'none' : 'block';
      const template = document.getElementById('transformation-template');
      perCaseDiv.innerHTML = template.innerHTML;
      
      // If we have stored custom transformations (as an array), prepopulate the UI.
      if (tc.transformations && tc.transformations.length > 0 && !tc.inheritSuiteTransformations) {
        // Loop over each transformation and apply it to the corresponding control.
        tc.transformations.forEach(trans => {
          // Find the corresponding checkbox by matching the value.
          const optionContainer = perCaseDiv.querySelector(`.transform-option input[type="checkbox"][value="${trans.type}"]`);
          if (optionContainer) {
            optionContainer.checked = true;
            // If a parameter is provided, set it in the sibling text input.
            if (trans.value) {
              const textInput = optionContainer.closest('.transform-option').querySelector('input[type="text"]');
              if (textInput) {
                textInput.value = trans.value;
              }
            }
          }
        });
      }
      
      // Listen for changes to update the test case data and transformation order display.
      perCaseDiv.addEventListener('input', function() {
        updateTestCaseData(tc, card);
        renderTransformationOrder(card, tc);
      });
      
      card.appendChild(perCaseDiv);

      // Container to display the transformation order.
      const orderDiv = document.createElement('div');
      orderDiv.className = 'transformation-order';
      card.appendChild(orderDiv);
      
      // Initialize the transformation order display.
      renderTransformationOrder(card, tc);

      // Remove button.
      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.textContent = 'Remove';
      removeBtn.className = 'remove-btn';
      removeBtn.onclick = () => {
        testCases.splice(index, 1);
        renderTestCases();
      };
      card.appendChild(removeBtn);

      container.appendChild(card);
    });
    document.getElementById('test_cases_data').value = JSON.stringify(testCases);
  }

  // Handler for adding an empty test case.
  document.getElementById('addTestCaseBtn').addEventListener('click', function() {
    testCases.push({ 
      prompt: '', 
      inheritSuiteTransformations: true, 
      transformations: [] 
    });
    renderTestCases();
  });

  // Handler for importing test cases from the text area.
  document.getElementById('importTestCasesBtn').addEventListener('click', function() {
    const importText = document.getElementById('test_cases_import').value;
    const lines = importText.split('\n').map(line => line.trim()).filter(line => line !== '');
    lines.forEach(line => {
      // Always add a new test case even if the prompt is the same.
      testCases.push({ 
        prompt: line, 
        inheritSuiteTransformations: true, 
        transformations: [] 
      });
    });
    renderTestCases();
  });

  // Handler for clicking on an orphaned test case.
  const orphanedContainer = document.getElementById('orphaned-test-cases-list');
  orphanedContainer.addEventListener('click', function(event) {
    if (event.target && event.target.nodeName === 'LI') {
      const prompt = event.target.getAttribute('data-prompt');
      const storedTransformations = event.target.getAttribute('data-transformations');
      let transformations = [];
      if (storedTransformations && storedTransformations.trim() !== "" && storedTransformations.trim() !== "null") {
        try {
          transformations = JSON.parse(storedTransformations);
        } catch(e) {
          console.error("Error parsing stored transformations:", e);
        }
      }
      // Always add a new test case even if the prompt is the same.
      testCases.push({ 
        prompt: prompt, 
        inheritSuiteTransformations: true, 
        transformations: transformations 
      });
      renderTestCases();
    }
  });

  // On form submit, capture suite-level transformations and test cases data.
  document.getElementById('create-suite-form').addEventListener('submit', function() {
    // Capture suite-level transformations.
    const suiteTransConfigElements = document.querySelectorAll('.suite-transformation-container input[type="checkbox"]:checked');
    const suiteTransformations = [];
    suiteTransConfigElements.forEach(checkbox => {
      let transform = { type: checkbox.value };
      // Find associated text input if applicable.
      if (checkbox.value === "prepend_text" || checkbox.value === "postpend_text") {
        const optionContainer = checkbox.closest('.transform-option');
        if (optionContainer) {
          const textInput = optionContainer.querySelector('input[type="text"]');
          if (textInput && textInput.value.trim() !== "") {
            transform.value = textInput.value.trim();
          }
        }
      }
      suiteTransformations.push(transform);
    });
    document.getElementById('suite_transformations').value = JSON.stringify(suiteTransformations);
    document.getElementById('test_cases_data').value = JSON.stringify(testCases);
  });

});

