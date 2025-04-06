document.addEventListener("DOMContentLoaded", function() {
  // Global array holding the dynamic test case objects.
  // Each object has: prompt, inheritSuiteTransformations (boolean), and transformations (array).
  let testCases = [];

  // Helper: Initialize event listeners for the transformation controls in a given container.
  // This function sets up listeners on each checkbox and its sibling text input.
  function setupTransformationListeners(container, testCase) {
    // Get all checkboxes within the container.
    const checkboxes = container.querySelectorAll('input[type="checkbox"]');

    checkboxes.forEach(checkbox => {
      // On change, update the testCase.transformations array to preserve the check order.
      checkbox.addEventListener('change', function() {
        const transformType = checkbox.value;
        // Find the sibling text input if any.
        const optionContainer = checkbox.closest('.transform-option');
        let associatedValue = "";
        if (optionContainer) {
          const textInput = optionContainer.querySelector('input[type="text"]');
          if (textInput) {
            associatedValue = textInput.value.trim();
          }
        }
        if (checkbox.checked) {
          // When checked, add the transformation at the end of the array.
          testCase.transformations.push({ type: transformType, value: associatedValue });
        } else {
          // When unchecked, remove any transformation with this type.
          testCase.transformations = testCase.transformations.filter(t => t.type !== transformType);
        }
        updateTestCasesData();
        renderTransformationOrder(findCardForTestCase(testCase), testCase);
      });
    });

    // Also attach listeners to any text inputs so that when their value changes,
    // the corresponding transformation object in testCase.transformations is updated.
    const textInputs = container.querySelectorAll('input[type="text"]');
    textInputs.forEach(input => {
      input.addEventListener('input', function() {
        // Determine the transformation type from the parent's checkbox.
        const optionContainer = input.closest('.transform-option');
        if (!optionContainer) return;
        const checkbox = optionContainer.querySelector('input[type="checkbox"]');
        if (!checkbox) return;
        const transformType = checkbox.value;
        // Find the transformation in the testCase array.
        let found = false;
        testCase.transformations = testCase.transformations.map(t => {
          if (t.type === transformType) {
            found = true;
            return { type: transformType, value: input.value.trim() };
          }
          return t;
        });
        // If not found (and checkbox is checked) then add it.
        if (checkbox.checked && !found) {
          testCase.transformations.push({ type: transformType, value: input.value.trim() });
        }
        updateTestCasesData();
        renderTransformationOrder(findCardForTestCase(testCase), testCase);
      });
    });
  }

  // Finds the card element associated with a given testCase object by searching for the matching data-index.
  function findCardForTestCase(testCase) {
    const container = document.getElementById('testCasesContainer');
    // We assume testCases are rendered in order.
    const cards = container.querySelectorAll('.test-case-card');
    // Loop over the cards and find one whose "data-index" matches the index of testCase in testCases.
    for (let i = 0; i < cards.length; i++) {
      if (JSON.parse(cards[i].getAttribute('data-index')) === testCases.indexOf(testCase)) {
        return cards[i];
      }
    }
    return null;
  }

  // Update the hidden input that holds JSON data for test cases.
  function updateTestCasesData() {
    document.getElementById('test_cases_data').value = JSON.stringify(testCases);
  }

  // Render the transformation order for a test case card.
  function renderTransformationOrder(card, testCase) {
    const orderContainer = card.querySelector('.transformation-order');
    orderContainer.innerHTML = ''; // Clear previous content

    if (testCase.inheritSuiteTransformations) {
      orderContainer.textContent = 'Using suite-level transformations.';
    } else {
      if (!testCase.transformations || testCase.transformations.length === 0) {
        orderContainer.textContent = 'No custom transformations set.';
        return;
      }
      // Create an ordered list that reflects the order in which transformations were checked.
      const ol = document.createElement('ol');
      testCase.transformations.forEach(t => {
        const li = document.createElement('li');
        li.textContent = t.type + (t.value ? ` (Parameter: ${t.value})` : '');
        ol.appendChild(li);
      });
      orderContainer.appendChild(ol);
    }
  }

  // Toggle display of the per-test-case transformation section.
  function toggleTransformationsSection(card, useSuiteLevel) {
    const perCaseDiv = card.querySelector('.per-case-transformations');
    perCaseDiv.style.display = useSuiteLevel ? 'none' : 'block';
  }

  // Render all dynamic test case cards.
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
      promptInput.oninput = e => { tc.prompt = e.target.value; updateTestCasesData(); };
      card.appendChild(promptInput);

      // Checkbox for inheriting suite-level transformations
      const inheritLabel = document.createElement('label');
      inheritLabel.textContent = ' Use suite-level transformations';
      const inheritCheckbox = document.createElement('input');
      inheritCheckbox.type = 'checkbox';
      inheritCheckbox.checked = tc.inheritSuiteTransformations !== false;
      inheritCheckbox.onchange = e => {
        tc.inheritSuiteTransformations = e.target.checked;
        // If switching to suite-level, clear any custom transformation order.
        if (e.target.checked) {
          tc.transformations = [];
        }
        toggleTransformationsSection(card, e.target.checked);
        updateTestCasesData();
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
      
      // If there are stored transformations in this test case, prepopulate the UI.
      if (tc.transformations && tc.transformations.length > 0 && !tc.inheritSuiteTransformations) {
        // For each transformation stored, check the corresponding checkbox and set the value if applicable.
        tc.transformations.forEach(trans => {
          const optionContainer = perCaseDiv.querySelector(`.transform-option input[type="checkbox"][value="${trans.type}"]`);
          if (optionContainer) {
            optionContainer.checked = true;
            if (trans.value) {
              const textInput = optionContainer.closest('.transform-option').querySelector('input[type="text"]');
              if (textInput) {
                textInput.value = trans.value;
              }
            }
          }
        });
      }
      // Setup event listeners on the transformation controls.
      setupTransformationListeners(perCaseDiv, tc);

      // Listen for any additional input events in the container.
      perCaseDiv.addEventListener('input', function() {
        updateTestCasesData();
        renderTransformationOrder(card, tc);
      });
      card.appendChild(perCaseDiv);

      // Container to display the transformation order.
      const orderDiv = document.createElement('div');
      orderDiv.className = 'transformation-order';
      card.appendChild(orderDiv);
      renderTransformationOrder(card, tc);

      // Remove button for the test case.
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
    updateTestCasesData();
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

  // On form submit, capture suite-level transformations and test case data.
  document.getElementById('create-suite-form').addEventListener('submit', function() {
    // Capture suite-level transformations.
    const suiteTransConfigElements = document.querySelectorAll('.suite-transformation-container input[type="checkbox"]:checked');
    const suiteTransformations = [];
    suiteTransConfigElements.forEach(checkbox => {
      let transform = { type: checkbox.value };
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