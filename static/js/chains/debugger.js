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

    function updateStepModal(stepId, executionData) {
        const requestDetailsEl = document.getElementById(`step-${stepId}-request-details`);
        const responseDetailsEl = document.getElementById(`step-${stepId}-response-details`);
        const contextDetailsEl = document.getElementById(`step-${stepId}-context-details`);

        if (executionData.error) {
            // Handle error case
            requestDetailsEl.innerHTML = `<div style="background: rgba(220, 53, 69, 0.1); border: 1px solid var(--danger-color, #dc3545); color: var(--danger-color, #dc3545); padding: 0.5rem; border-radius: 4px;">Step execution failed before request could be sent</div>`;
            responseDetailsEl.innerHTML = `<div style="background: rgba(220, 53, 69, 0.1); border: 1px solid var(--danger-color, #dc3545); color: var(--danger-color, #dc3545); padding: 0.5rem; border-radius: 4px;"><strong>Error:</strong> ${executionData.error}</div>`;
            contextDetailsEl.innerHTML = `<pre class="debug-json">${JSON.stringify(executionData.context, null, 2)}</pre>`;
        } else {
            // Handle successful execution
            if (executionData.request) {
                let requestHtml = '';
                if (executionData.request.payload_template) {
                    requestHtml += `<div class="debug-item" style="margin-bottom: 1rem;">
                        <strong>Payload Template:</strong>
                        <pre class="debug-json">${executionData.request.payload_template}</pre>
                    </div>`;
                }
                if (executionData.request.payload) {
                    requestHtml += `<div class="debug-item" style="margin-bottom: 1rem;">
                        <strong>Final Rendered Payload:</strong>
                        <pre class="debug-json">${JSON.stringify(executionData.request.payload, null, 2)}</pre>
                    </div>`;
                }
                requestDetailsEl.innerHTML = requestHtml || '<p style="color: var(--text-muted-color, #888);">No request details available</p>';
            }

            if (executionData.response) {
                let responseHtml = `<div class="debug-item" style="margin-bottom: 1rem;">
                    <strong>Status Code:</strong> `;
                
                if (executionData.response.status_code >= 200 && executionData.response.status_code < 300) {
                    responseHtml += `<span style="background: var(--success-color, #28a745); color: white; padding: 0.25rem 0.5rem; border-radius: 4px;">${executionData.response.status_code}</span>`;
                } else if (executionData.response.status_code >= 400) {
                    responseHtml += `<span style="background: var(--danger-color, #dc3545); color: white; padding: 0.25rem 0.5rem; border-radius: 4px;">${executionData.response.status_code}</span>`;
                } else {
                    responseHtml += `<span style="background: var(--warning-color, #ffc107); color: black; padding: 0.25rem 0.5rem; border-radius: 4px;">${executionData.response.status_code}</span>`;
                }
                
                responseHtml += `</div>`;
                
                if (executionData.response.body) {
                    responseHtml += `<div class="debug-item" style="margin-bottom: 1rem;">
                        <strong>Response Body:</strong>
                        <pre class="debug-json">${JSON.stringify(executionData.response.body, null, 2)}</pre>
                    </div>`;
                }
                responseDetailsEl.innerHTML = responseHtml;
            }

            if (executionData.context) {
                contextDetailsEl.innerHTML = `<pre class="debug-json">${JSON.stringify(executionData.context, null, 2)}</pre>`;
            }
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
            // Hide debug buttons
            const debugBtn = s.querySelector('.step-debug-btn');
            if (debugBtn) {
                debugBtn.style.display = 'none';
            }
        });
        
        // Reset all modal content
        steps.forEach(step => {
            const stepId = step.dataset.stepId;
            const requestDetailsEl = document.getElementById(`step-${stepId}-request-details`);
            const responseDetailsEl = document.getElementById(`step-${stepId}-response-details`);
            const contextDetailsEl = document.getElementById(`step-${stepId}-context-details`);
            
            if (requestDetailsEl) requestDetailsEl.innerHTML = '<p style="color: var(--text-muted-color, #888);">Execute this step to see request details</p>';
            if (responseDetailsEl) responseDetailsEl.innerHTML = '<p style="color: var(--text-muted-color, #888);">Execute this step to see response details</p>';
            if (contextDetailsEl) contextDetailsEl.innerHTML = '<p style="color: var(--text-muted-color, #888);">Execute this step to see context variables</p>';
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
                
                // Update modal with error details
                updateStepModal(stepId, {
                    error: result.error,
                    context: context
                });
                
                // Show debug button for error cases
                const debugBtn = currentStepElement.querySelector('.step-debug-btn');
                if (debugBtn) {
                    debugBtn.style.display = 'inline-block';
                }
                
                return; // Stop execution on error
            }
            
            currentStepElement.classList.add('success');
            context = { ...context, ...result.new_context_variables };
            
            prettyPrintJson(document.getElementById('last-request-template'), result.request.payload_template);
            prettyPrintJson(document.getElementById('last-request'), result.request.payload);
            document.getElementById('response-status-result').textContent = result.response.status_code;
            prettyPrintJson(document.getElementById('last-response'), result.response.body);
            
            // Update modal with execution details
            updateStepModal(stepId, {
                request: result.request,
                response: result.response,
                context: context
            });
            
            // Show debug button after successful execution
            const debugBtn = currentStepElement.querySelector('.step-debug-btn');
            if (debugBtn) {
                debugBtn.style.display = 'inline-block';
            }
            
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
            
            // Update modal with network error details
            updateStepModal(stepId, {
                error: `Network/Server Error: ${err.message}`,
                context: context
            });
            
            // Show debug button for network errors
            const debugBtn = currentStepElement.querySelector('.step-debug-btn');
            if (debugBtn) {
                debugBtn.style.display = 'inline-block';
            }
            
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