// static/js/testSuites/list_test_suites.js

// Ensure csrfToken is defined globally in your HTML template before this script is loaded.
// Example in HTML: <script>const csrfToken = "{{ csrf_token() }}";</script>

let importData = null; // Holds the data from the imported JSON file

document.addEventListener('DOMContentLoaded', function() {
  // Initialize filter config for the suites table
  // Assumes filterCommon.js is loaded and window.initializeFilter is available
  if (window.initializeFilter) {
    window.filterConfigs = [
      {
        searchInputId: "searchSuite",
        tableId: "suitesTable",
        toggleButtonSelector: ".view-test-cases-btn",
        rowGroupSize: 2, // Each suite has a main row and a test cases row
        viewDetailsText: "View Test Cases",
        hideDetailsText: "Hide Test Cases"
      }
    ];
    window.initializeFilter(); // Initialize the filter
  } else {
    console.warn("filterCommon.js or initializeFilter function not found. Table filtering will not work.");
  }

  // Initialize modal event listeners
  const modal = document.getElementById('importModal');
  const closeBtn = modal ? modal.querySelector('.modal-header .close') : null;
  const cancelBtn = modal ? modal.querySelector('.modal-footer button[onclick="closeImportModal()"]') : null;


  if (closeBtn) {
    closeBtn.onclick = closeImportModal;
  }
  if (cancelBtn) {
    // Ensure the cancel button in the modal footer also closes the modal
    cancelBtn.onclick = closeImportModal;
  }

  // Close modal if user clicks outside of it
  window.onclick = function(event) {
    if (event.target === modal) {
      closeImportModal();
    }
  };

  // Event listener for the actual file input
  const importFileInput = document.getElementById('importFile');
  if (importFileInput) {
    importFileInput.addEventListener('change', function() {
      handleFileSelect(this);
    });
  }

  // Event listeners for modal buttons (if they exist)
  const selectAllBtn = document.querySelector('button[onclick="selectAllSuites()"]');
  if (selectAllBtn) {
      selectAllBtn.onclick = selectAllSuites;
  }

  const deselectAllBtn = document.querySelector('button[onclick="deselectAllSuites()"]');
  if (deselectAllBtn) {
      deselectAllBtn.onclick = deselectAllSuites;
  }

  const importSelectedBtn = document.querySelector('button[onclick="importSelectedSuites()"]');
  if (importSelectedBtn) {
      importSelectedBtn.onclick = importSelectedSuites;
  }
});

function handleFileSelect(inputElement) {
  if (!inputElement.files || !inputElement.files[0]) {
    console.log("No file selected.");
    return;
  }

  const file = inputElement.files[0];
  const reader = new FileReader();

  reader.onload = function(e) {
    try {
      const data = JSON.parse(e.target.result);

      if (data.version !== '1.0') {
        alert('Unsupported file version. Expected version 1.0.');
        return;
      }

      // Always expect a "test_suites" array
      if (data.test_suites && Array.isArray(data.test_suites)) {
        if (data.test_suites.length === 0) {
          alert('No test suites found in the file.');
          return;
        }
        importData = data; // Store the full data
        showImportModal(data.test_suites);
      } else {
        alert('Invalid file format: "test_suites" array not found or not an array.');
      }
    } catch (error) {
      alert('Error reading or parsing file: ' + error.message);
      console.error("File parsing error:", error);
    }
  };

  reader.onerror = function() {
    alert('Error reading file.');
    console.error("FileReader error:", reader.error);
  };

  reader.readAsText(file);
  inputElement.value = ''; // Reset file input to allow re-selection of the same file
}

function showImportModal(suites) {
  const modal = document.getElementById('importModal');
  const suiteList = document.getElementById('suiteList');

  if (!modal || !suiteList) {
    console.error("Import modal or suite list element not found.");
    return;
  }

  suiteList.innerHTML = ''; // Clear existing content

  suites.forEach((suite, index) => {
    const suiteDiv = document.createElement('div');
    suiteDiv.className = 'suite-item';
    // Note: Removed transformation details as per requirements
    suiteDiv.innerHTML = `
      <div class="suite-header">
        <input type="checkbox" id="suite-${index}" data-suite-index="${index}" checked>
        <label for="suite-${index}">${suite.description || 'No Description'}</label>
      </div>
      <div class="suite-details">
        <p><strong>Behavior:</strong> ${suite.behavior || 'N/A'}</p>
        <p><strong>Objective:</strong> ${suite.objective || 'N/A'}</p>
        <p><strong>Test Cases:</strong> ${suite.test_cases ? suite.test_cases.length : 0}</p>
      </div>
    `;
    suiteList.appendChild(suiteDiv);
  });

  modal.style.display = 'block';
}

function closeImportModal() {
  const modal = document.getElementById('importModal');
  if (modal) {
    modal.style.display = 'none';
  }
  importData = null; // Clear the stored data
}

function selectAllSuites() {
  const checkboxes = document.querySelectorAll('#suiteList .suite-item input[type="checkbox"]');
  checkboxes.forEach(checkbox => checkbox.checked = true);
}

function deselectAllSuites() {
  const checkboxes = document.querySelectorAll('#suiteList .suite-item input[type="checkbox"]');
  checkboxes.forEach(checkbox => checkbox.checked = false);
}

async function importSelectedSuites() {
  if (!importData || !importData.test_suites) {
    alert('No import data available. Please select a file first.');
    return;
  }

  const selectedSuitesData = [];
  const checkboxes = document.querySelectorAll('#suiteList .suite-item input[type="checkbox"]');

  checkboxes.forEach(checkbox => {
    if (checkbox.checked) {
      const index = parseInt(checkbox.dataset.suiteIndex, 10);
      if (importData.test_suites[index]) {
        selectedSuitesData.push(importData.test_suites[index]);
      }
    }
  });

  if (selectedSuitesData.length === 0) {
    alert('Please select at least one test suite to import.');
    return;
  }

  const dataToSubmit = {
    version: importData.version || '1.0', // Use version from file or default
    test_suites: selectedSuitesData
  };

  try {
    // Ensure csrfToken is available (should be defined globally by the template)
    if (typeof csrfToken === 'undefined') {
        alert('CSRF token not found. Cannot proceed with import.');
        console.error('csrfToken is not defined.');
        return;
    }

    const response = await fetch('/test_suites/import_suite', { // Endpoint matches your existing HTML
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify(dataToSubmit)
    });

    const result = await response.json();

    if (response.ok) {
      alert(`Successfully imported ${result.suites_imported_count || result.suites_imported || 0} test suite(s)!`); // Adjusted to common success keys
      window.location.reload();
    } else if (response.status === 409) { // Conflict - Duplicates
        if (result.error === 'duplicates_found' && result.duplicates) {
            const duplicateDescriptions = result.duplicates.map(d =>
                `- "${d.description}" (Behavior: ${d.behavior || 'N/A'})`
            ).join('\n');

            // More robust message construction
            let message = `Found ${result.duplicate_count || 0} duplicate test suite(s) out of ${result.total_suites_in_file || selectedSuitesData.length} selected for import:\n\n${duplicateDescriptions}\n\n`;
            message += `The backend currently does not support skipping individual duplicates.`;
            message += `Please adjust your import file or the existing suites.`;
            alert(message);
        } else {
             alert(`Conflict: ${result.message || result.error || 'An unknown conflict occurred.'}`);
        }
    } else {
      alert(`Error importing test suites: ${result.message || result.error || 'An unknown error occurred.'}`);
    }
  } catch (error) {
    alert('An error occurred during the import process: ' + error.message);
    console.error("Import submission error:", error);
  } finally {
    closeImportModal();
  }
}