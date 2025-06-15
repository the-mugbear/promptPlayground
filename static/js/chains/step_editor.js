document.addEventListener('DOMContentLoaded', function () {
    const testBtn = document.getElementById('test-step-btn');
    if (!testBtn) return;

    const csrfToken = document.getElementById('csrf_token')?.value;
    if (!csrfToken) {
        console.error("CSRF token not found. AJAX POST requests will be blocked.");
    }

    /**
     * A helper function to safely find an element by its ID.
     * If the element is not found, it shows an alert for debugging.
     * @param {string} id The ID of the element to find.
     * @returns {HTMLElement|null} The found element or null.
     */
    function findEl(id) {
        const el = document.getElementById(id);
        if (!el) {
            // This alert is for us, the developers, to fix the code.
            alert(`Developer Error: A required element with id="${id}" was not found on the page. Please check the HTML template and the JavaScript.`);
            return null;
        }
        return el;
    }

    /**
     * A helper function to safely pretty-print JSON.
     * @param {HTMLElement} element The element to put the text into.
     * @param {any} data The data to print.
     */
    function prettyPrintJson(element, data) {
        if (!element) return;
        try {
            const text = (typeof data === 'string') ? data : JSON.stringify(data, null, 2);
            const jsonObj = JSON.parse(text);
            element.textContent = JSON.stringify(jsonObj, null, 2);
        } catch (e) {
            element.textContent = (typeof data === 'string') ? data : String(data);
        }
    }

    testBtn.addEventListener('click', function () {
        // --- Defensively find all required form elements ---
        const endpointEl = findEl('endpoint');
        const payloadEl = findEl('payload');
        const headersEl = findEl('headers');
        const dataExtractionRulesEl = findEl('data_extraction_rules');
        const mockContextEl = findEl('mock_context');

        // If any element was not found, the helper will show an alert and we stop here.
        if (!endpointEl || !payloadEl || !headersEl || !dataExtractionRulesEl || !mockContextEl) {
            return;
        }

        const resultsContainer = findEl('test-results-container');
        let dataExtractionRules, mockContext;

        // Safely parse JSON inputs
        try {
            dataExtractionRules = JSON.parse(dataExtractionRulesEl.value || '[]');
        } catch (e) {
            alert('Error: Data Extraction Rules contain invalid JSON.');
            return;
        }

        try {
            mockContext = JSON.parse(mockContextEl.value || '{}');
            mockContextEl.classList.remove('is-invalid');
        } catch (e) {
            mockContextEl.classList.add('is-invalid');
            findEl('mock-context-error').textContent = 'Invalid JSON format for Mock Context.';
            return;
        }

        // Show loading state
        testBtn.disabled = true;
        testBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        resultsContainer.style.display = 'none';

        fetch('/api/chains/test_step_in_isolation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken 
            },
            body: JSON.stringify({
                // Use the element values directly
                endpoint_id: endpointEl.value,
                payload: payloadEl.value,
                headers: headersEl.value,
                data_extraction_rules: dataExtractionRules,
                mock_context: mockContext
            })
        })
            .then(response => {
                // First, check if the response from the server was successful
                if (!response.ok) {
                    // If not, create a descriptive error to be caught below
                    throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
                }
                // If the response was successful, we can safely parse it as JSON
                return response.json();
            })
            .then(data => {
                resultsContainer.style.display = 'block';

                if (data.error) {
                    findEl('test-response-body-result').textContent = `Error: ${data.error}`;
                    return;
                }

                prettyPrintJson(findEl('rendered-payload-result'), data.rendered_payload);
                findEl('test-response-status-result').textContent = data.response.status_code;
                prettyPrintJson(findEl('test-response-body-result'), data.response.body);
                prettyPrintJson(findEl('extracted-data-result'), data.extracted_data);
            })
            .catch(error => {
                // This will now catch both network errors and the server status error from above
                resultsContainer.style.display = 'block';
                const errorResultEl = findEl('test-response-body-result');
                if (errorResultEl) {
                    errorResultEl.textContent = `An error occurred: ${error.message}. Please check the API endpoint and server logs.`;
                }
                console.error('Error testing step:', error);
            })
            .finally(() => {
                testBtn.disabled = false;
                testBtn.innerHTML = '<i class="fas fa-play"></i> Test This Step';
            });
    });
});