document.addEventListener('DOMContentLoaded', function() {
    let context = {};
    let currentStepIndex = 0;
    const steps = Array.from(document.querySelectorAll('#steps-list .list-group-item'));

    const runNextBtn = document.getElementById('run-next-btn');
    const resetBtn = document.getElementById('reset-btn');
    const currentContextEl = document.getElementById('current-context');
    const lastRequestEl = document.getElementById('last-request');
    const lastResponseEl = document.getElementById('last-response');
    const responseStatusEl = document.getElementById('response-status-result');

    // Helper to pretty-print JSON safely
    function prettyPrintJson(element, jsonString) {
        try {
            // Check if the string is already a JSON object (from parsing before)
            const jsonObj = (typeof jsonString === 'string') ? JSON.parse(jsonString) : jsonString;
            element.textContent = JSON.stringify(jsonObj, null, 2);
        } catch (e) {
            element.textContent = jsonString; // Show as raw text if not valid JSON
        }
    }

    function resetDebugger() {
        context = {};
        currentStepIndex = 0;
        lastRequestEl.textContent = '';
        lastResponseEl.textContent = '';
        responseStatusEl.textContent = '';
        steps.forEach(s => s.classList.remove('active', 'list-group-item-success', 'list-group-item-danger'));
        updateUI();
    }

    function updateUI() {
        prettyPrintJson(currentContextEl, context);
        runNextBtn.disabled = currentStepIndex >= steps.length;
    }

    runNextBtn.addEventListener('click', function() {
        if (currentStepIndex >= steps.length) return;

        const currentStepElement = steps[currentStepIndex];
        const stepId = currentStepElement.dataset.stepId;
        
        runNextBtn.disabled = true;
        currentStepElement.classList.add('active');
        currentStepElement.classList.remove('list-group-item-success', 'list-group-item-danger');

        fetch('/api/chains/execute_step', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ step_id: stepId, context: context })
        })
        .then(response => response.json())
        .then(result => {
            currentStepElement.classList.remove('active');

            if (result.error) {
                currentStepElement.classList.add('list-group-item-danger');
                responseStatusEl.textContent = 'Error';
                lastResponseEl.textContent = `Execution Error: ${result.error}`;
                return;
            }
            
            currentStepElement.classList.add('list-group-item-success');
            context = { ...context, ...result.new_context_variables };
            
            prettyPrintJson(lastRequestEl, result.request.payload);
            responseStatusEl.textContent = result.response.status_code;
            prettyPrintJson(lastResponseEl, result.response.body);
            
            currentStepIndex++;
            updateUI();
        })
        .catch(err => {
            currentStepElement.classList.remove('active');
            currentStepElement.classList.add('list-group-item-danger');
            responseStatusEl.textContent = 'Failed';
            lastResponseEl.textContent = `An unexpected network or server error occurred.`;
            console.error('Error executing step:', err);
        })
        .finally(() => {
            runNextBtn.disabled = currentStepIndex >= steps.length;
        });
    });

    resetBtn.addEventListener('click', resetDebugger);

    resetDebugger(); // Initialize the view
});