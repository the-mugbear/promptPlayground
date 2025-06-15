document.addEventListener('DOMContentLoaded', function() {
    let context = {};
    let currentStepIndex = 0;
    const steps = Array.from(document.querySelectorAll('#steps-list .list-group-item'));

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (!csrfToken) {
        console.error("CSRF token meta tag not found. AJAX POST requests will be blocked.");
    }

    const runNextBtn = document.getElementById('run-next-btn');
    const resetBtn = document.getElementById('reset-btn');
    const currentContextEl = document.getElementById('current-context');
    const lastRequestEl = document.getElementById('last-request');
    const lastResponseEl = document.getElementById('last-response');
    const responseStatusEl = document.getElementById('response-status-result');

    function prettyPrintJson(element, jsonString) {
        try {
            const jsonObj = (typeof jsonString === 'string') ? JSON.parse(jsonString) : jsonString;
            element.textContent = JSON.stringify(jsonObj, null, 2);
        } catch (e) {
            element.textContent = jsonString;
        }
    }

    // Function to update the highlight for the current step
    function updateCurrentStepHighlight() {
        steps.forEach((step, index) => {
            step.classList.remove('current-step');
            if (index === currentStepIndex) {
                step.classList.add('current-step');
            }
        });
    }

    function resetDebugger() {
        context = {};
        currentStepIndex = 0;
        
        // Clear all results and status classes from steps
        lastRequestEl.textContent = 'No request sent yet.';
        lastResponseEl.textContent = 'No response received yet.';
        responseStatusEl.textContent = 'N/A';
        steps.forEach(s => {
            s.classList.remove('active', 'success', 'error', 'current-step');
        });
        
        updateUI();
        updateCurrentStepHighlight(); // Highlight the first step
        console.log('Debugger reset.');
    }

    function updateUI() {
        prettyPrintJson(currentContextEl, context);
        runNextBtn.disabled = currentStepIndex >= steps.length;
    }

    runNextBtn.addEventListener('click', function() {
        if (currentStepIndex >= steps.length) return;

        const currentStepElement = steps[currentStepIndex];
        const stepId = currentStepElement.dataset.stepId;
        
        // Update UI for the running step
        runNextBtn.disabled = true;
        currentStepElement.classList.remove('success', 'error');
        currentStepElement.classList.add('active');

        fetch('/api/chains/execute_step', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ step_id: stepId, context: context })
        })
        .then(response => response.json())
        .then(result => {
            currentStepElement.classList.remove('active');

            if (result.error) {
                currentStepElement.classList.add('error');
                responseStatusEl.textContent = 'Error';
                lastResponseEl.textContent = `Execution Error: ${result.error}`;
                return; // Stop execution on error
            }
            
            currentStepElement.classList.add('success');
            context = { ...context, ...result.new_context_variables };
            
            prettyPrintJson(lastRequestEl, result.request.payload);
            responseStatusEl.textContent = result.response.status_code;
            prettyPrintJson(lastResponseEl, result.response.body);
            
            // Move to the next step
            currentStepIndex++;
            updateUI();
            updateCurrentStepHighlight(); // Highlight the next step
        })
        .catch(err => {
            currentStepElement.classList.remove('active');
            currentStepElement.classList.add('error');
            responseStatusEl.textContent = 'Failed';
            lastResponseEl.textContent = `An unexpected network or server error occurred.`;
            console.error('Error executing step:', err);
        })
        .finally(() => {
            // Only re-enable the button if there are more steps
            runNextBtn.disabled = currentStepIndex >= steps.length;
        });
    });

    resetBtn.addEventListener('click', resetDebugger);

    // Initialize the view on page load
    resetDebugger();
});