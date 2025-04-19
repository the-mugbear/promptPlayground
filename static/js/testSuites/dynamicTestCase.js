// dynamicTestCase.js

document.addEventListener("DOMContentLoaded", function() {
  // --- GLOBAL STATE -------------------------------------------------------
  let testCases = [];

  // --- HELPERS ------------------------------------------------------------
  function debounce(func, wait) {
    let timeout;
    return function(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }
  function updateTestCasesData() {
    document.getElementById('test_cases_data').value = JSON.stringify(testCases);
  }

  // --- SUITE‑LEVEL TRANSFORMS ----------------------------------------------
  function getSuiteTransforms() {
    const checkedBoxes = document.querySelectorAll(
      '.transformations-container input[type="checkbox"]:checked'
    );
    return Array.from(checkedBoxes).map(cb => {
      const tr = { type: cb.value };
      if (cb.value === 'prepend_text' || cb.value === 'postpend_text') {
        const opt = cb.closest('.transform-option');
        const txt = opt.querySelector('input[type="text"]');
        if (txt && txt.value !== "") tr.value = txt.value;
      }
      return tr;
    });
  }
  function updateAllInheritedPreviews() {
    const defaults = getSuiteTransforms();
    testCases.forEach(tc => {
      if (tc.inheritSuiteTransformations) {
        tc.transformations = JSON.parse(JSON.stringify(defaults));
      }
    });
    document.querySelectorAll('.test-case-card').forEach(card => {
      const idx = parseInt(card.dataset.index, 10);
      const tc  = testCases[idx];
      const perCase = card.querySelector('.per-case-transformations');
      perCase.style.display = tc.inheritSuiteTransformations ? 'none' : 'block';
      renderTransformationOrder(card, tc);
      updatePreview(
        card.querySelector('.per-case-transformations'),
        card.querySelector('textarea'),
        card.querySelector('.preview-output'),
        tc
      );
    });
    updateTestCasesData();
  }
  document.querySelectorAll(
    '.transformations-container input[type="checkbox"], ' +
    '.transformations-container input[type="text"]'
  ).forEach(ctrl => {
    ctrl.addEventListener('change', updateAllInheritedPreviews);
  });

  // --- RENDER & CARD CREATION ---------------------------------------------
  function createTestCaseCard(tc, index) {
    const card = document.createElement('div');
    card.className = 'test-case-card';
    card.dataset.index = index;

    // Prompt
    const promptInput = document.createElement('textarea');
    promptInput.className = 'form-control';
    promptInput.rows = 3;
    promptInput.placeholder = 'Enter test case prompt';
    promptInput.value = tc.prompt || '';
    card.appendChild(promptInput);

    // Preview
    const previewDiv = document.createElement('div');
    previewDiv.className = 'transformation-preview';
    previewDiv.innerHTML = '<strong>Preview:</strong> <span class="preview-output"></span>';
    card.appendChild(previewDiv);

    // Inherit‑suite checkbox
    const inheritLabel = document.createElement('label');
    inheritLabel.className = 'form-label';
    inheritLabel.textContent = ' Use suite-level transformations';
    const inheritCheckbox = document.createElement('input');
    inheritCheckbox.type = 'checkbox';
    inheritCheckbox.checked = tc.inheritSuiteTransformations !== false;
    inheritCheckbox.addEventListener('change', e => {
      tc.inheritSuiteTransformations = e.target.checked;
      const perCase = card.querySelector('.per-case-transformations');
      perCase.style.display = e.target.checked ? 'none' : 'block';
      updateTestCasesData();
      renderTransformationOrder(card, tc);
      if (e.target.checked) {
        tc.transformations = JSON.parse(JSON.stringify(getSuiteTransforms()));
        updatePreview(
          perCase,
          promptInput,
          card.querySelector('.preview-output'),
          tc
        );
      }
    });
    inheritLabel.insertBefore(inheritCheckbox, inheritLabel.firstChild);
    card.appendChild(inheritLabel);

    // Per‑case transforms
    const transformationsContainer = document.createElement('div');
    transformationsContainer.className = 'per-case-transformations';
    transformationsContainer.innerHTML =
      document.getElementById('transformation-template').innerHTML;
    if (tc.inheritSuiteTransformations) {
      transformationsContainer.style.display = 'none';
    }
    card.appendChild(transformationsContainer);

    // Sync cloned checkboxes & text inputs
    tc.transformations.forEach(tr => {
      const cb = transformationsContainer.querySelector(
        `input[name="transformations"][value="${tr.type}"]`
      );
      if (!cb) return;
      cb.checked = true;
      if (tr.type === 'prepend_text' || tr.type === 'postpend_text') {
        const inputName = tr.type === 'prepend_text'
          ? 'text_to_prepend'
          : 'text_to_postpend';
        const txt = transformationsContainer.querySelector(`input[name="${inputName}"]`);
        if (txt) txt.value = tr.value;
      }
    });

    // Error & order
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    card.appendChild(errorDiv);
    const orderDiv = document.createElement('div');
    orderDiv.className = 'transformation-order';
    card.appendChild(orderDiv);

    // Actions
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'test-case-actions';

    // Move Up
    const moveUpBtn = document.createElement('button');
    moveUpBtn.type = 'button';
    moveUpBtn.className = 'move-up-btn';
    moveUpBtn.textContent = '↑';
    moveUpBtn.addEventListener('click', e => {
      e.preventDefault();
      moveTestCase(card, -1);
    });
    actionsDiv.appendChild(moveUpBtn);

    // Move Down
    const moveDownBtn = document.createElement('button');
    moveDownBtn.type = 'button';
    moveDownBtn.className = 'move-down-btn';
    moveDownBtn.textContent = '↓';
    moveDownBtn.addEventListener('click', e => {
      e.preventDefault();
      moveTestCase(card, 1);
    });
    actionsDiv.appendChild(moveDownBtn);

    // Duplicate
    const duplicateBtn = document.createElement('button');
    duplicateBtn.type = 'button';
    duplicateBtn.className = 'duplicate-btn';
    duplicateBtn.textContent = 'Duplicate';
    duplicateBtn.addEventListener('click', e => {
      e.preventDefault();
      duplicateTestCase(card, index);
    });
    actionsDiv.appendChild(duplicateBtn);

    // Remove
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'remove-btn';
    removeBtn.textContent = 'Remove';
    removeBtn.addEventListener('click', e => {
      e.preventDefault();
      testCases.splice(index, 1);
      renderTestCases();
    });
    actionsDiv.appendChild(removeBtn);

    card.appendChild(actionsDiv);
    return card;
  }

  // --- EVENT BINDERS (NO DOUBLE-LISTENERS) -------------------------------
  function setupPromptInputListeners(card, tc) {
    const prompt = card.querySelector('textarea');
    const err    = card.querySelector('.error-message');
    prompt.addEventListener('input', () => err.textContent = '');
  }
  function setupTransformationControlListeners(card, tc) {
    const container   = card.querySelector('.per-case-transformations');
    const promptInput = card.querySelector('textarea');
    const previewOut  = card.querySelector('.preview-output');
    const debounced   = debounce(() => updatePreview(container, promptInput, previewOut, tc), 300);

    updatePreview(container, promptInput, previewOut, tc);

    container.querySelectorAll('input[type="checkbox"][name="transformations"]')
      .forEach(cb => cb.addEventListener('change', () => {
        if (cb.checked) {
          if (!tc.transformations.some(t => t.type === cb.value)) {
            tc.transformations.push({ type: cb.value, value: '' });
          }
        } else {
          tc.transformations = tc.transformations.filter(t => t.type !== cb.value);
        }
        updateTestCasesData();
        renderTransformationOrder(card, tc);
        debounced();
      }));

    container.querySelectorAll('input[type="text"]').forEach(input => {
      input.addEventListener('input', () => {
        const type = input.closest('.transform-option')
                          .querySelector('input[type="checkbox"]').value;
        tc.transformations = tc.transformations.map(t =>
          t.type === type ? { type, value: input.value } : t
        );
        updateTestCasesData();
        renderTransformationOrder(card, tc);
        debounced();
      });
    });

    promptInput.addEventListener('input', debounced);
  }

  // --- PREVIEW -------------------------------------------------------------
  function updatePreview(container, promptInput, previewOut, tc) {
    const lines = [promptInput.value];
    const types = tc.transformations.map(t => t.type);
    const params = {};

    if (tc.inheritSuiteTransformations) {
      tc.transformations.forEach(t => {
        if (t.type === 'prepend_text')  params.text_to_prepend  = t.value;
        if (t.type === 'postpend_text') params.text_to_postpend = t.value;
      });
    } else {
      container.querySelectorAll('input[type="text"]').forEach(i => {
        if (i.name === 'text_to_prepend')  params.text_to_prepend  = i.value;
        if (i.name === 'text_to_postpend') params.text_to_postpend = i.value;
      });
    }

    if (!lines[0].trim()) {
      previewOut.textContent = '';
      return;
    }

    const formEl     = document.getElementById('create-suite-form');
    const previewUrl = formEl.getAttribute('data-preview-url') || '/test_suites/preview_transform';

    fetch(previewUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lines, transformations: types, params })
    })
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(data => {
      previewOut.textContent = (data.transformed_lines || [])[0] || 'No preview';
    })
    .catch(err => {
      console.error('Preview error:', err);
      previewOut.textContent = `Error: ${err}`;
    });
  }

  // --- ORDER DISPLAY ------------------------------------------------------
  function renderTransformationOrder(card, tc) {
    const out = card.querySelector('.transformation-order');
    if (tc.inheritSuiteTransformations) {
      out.textContent = 'Using suite-level transformations.';
    } else if (!tc.transformations.length) {
      out.textContent = 'No custom transformations.';
    } else {
      out.textContent = 'Custom: ' + tc.transformations.map(t => t.type).join(', ');
    }
  }

  // --- MOVE / DUP / REMOVE ------------------------------------------------
  function moveTestCase(card, dir) {
    const i  = parseInt(card.dataset.index, 10);
    const ni = i + dir;
    if (ni < 0 || ni >= testCases.length) return;
    testCases.splice(ni, 0, testCases.splice(i, 1)[0]);
    renderTestCases();
  }
  function duplicateTestCase(card, i) {
    testCases.splice(i + 1, 0, JSON.parse(JSON.stringify(testCases[i])));
    renderTestCases();
  }

  // --- RENDER ALL ---------------------------------------------------------
  function renderTestCases() {
    const container = document.getElementById('testCasesContainer');
    container.innerHTML = '';
    testCases.forEach((tc, i) => {
      const card = createTestCaseCard(tc, i);

      // Validate prompt
      if (!card.querySelector('textarea').value.trim()) {
        card.querySelector('.error-message').textContent = 'Prompt is required.';
      }

      setupPromptInputListeners(card, tc);
      setupTransformationControlListeners(card, tc);
      renderTransformationOrder(card, tc);
      container.appendChild(card);
    });
    updateTestCasesData();
  }

  // --- IMPORT CASES -------------------------------------------------------
  document.getElementById('importTestCasesBtn').addEventListener('click', () => {
    const text  = document.getElementById('test_cases_import').value;
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
    const defaults = getSuiteTransforms();

    lines.forEach(line => {
      testCases.push({
        prompt: line,
        inheritSuiteTransformations: true,
        transformations: JSON.parse(JSON.stringify(defaults))
      });
    });

    renderTestCases();
  });

  // --- FORM SUBMIT --------------------------------------------------------
  document.getElementById('create-suite-form').addEventListener('submit', () => {
    const suiteTransforms = getSuiteTransforms();
    document.getElementById('suite_transformations').value =
      JSON.stringify(suiteTransforms);
    document.getElementById('test_cases_data').value =
      JSON.stringify(testCases);
  });

  // --- INIT ----------------------------------------------------------------
  renderTestCases();
});
