// static/js/testRuns/runMonitor.js
document.addEventListener('DOMContentLoaded', () => {
    // --- Get Elements ---
    const testRunDataElement = document.getElementById('test-run-data');
    if (!testRunDataElement) {
        // console.log("No test-run-data element found. SocketIO monitoring will not activate.");
        return; // Exit if no run context for this page
    }

    const testRunId = testRunDataElement.dataset.runId;
    let initialStatus = testRunDataElement.dataset.runStatus;
    // let initialCeleryTaskId = testRunDataElement.dataset.celeryTaskId; // For debugging if needed

    // UI Elements for status and progress
    const statusElement = document.getElementById('test-run-status');
    const progressBar = document.getElementById('test-run-progress-bar');
    const progressBarText = document.getElementById('progress-bar-text');
    const progressCounter = document.getElementById('progress-counter');
    const progressSection = document.getElementById('progress-section');

    // Control Buttons
    // The 'Start Full Run' button triggers a form POST, so it's not directly controlled by this JS for emitting.
    // We will manage the state (enabled/disabled) of the Start button though.
    const startButton = document.getElementById('start-run-button');
    const pauseButton = document.getElementById('pause-run-button');
    const resumeButton = document.getElementById('resume-run-button');
    const cancelButton = document.getElementById('cancel-run-button');

    // --- Ensure all critical UI elements are present ---
    if (!statusElement || !progressBar || !progressBarText || !progressCounter || !progressSection ||
        !startButton || !pauseButton || !resumeButton || !cancelButton) {
        console.error("One or more UI elements for test run monitoring are missing. Check IDs.");
        return;
    }

    // --- Socket.IO Connection ---
    // The Socket.IO server URL will be the same as the page's origin by default.
    // If your Socket.IO server is elsewhere, you need to specify: const socket = io('http://yourserver.com');
    const socket = io({
        transports:['websocket','polling'],
        reconnection: true,
        reconnectionDelayMax: 10000,   // up to 10 s
      });

    socket.on('connect', () => {
        console.log(`Socket.IO connected: ${socket.id} for TestRun ID: ${testRunId}`);
        // Join the room specific to this test run
        socket.emit('join_test_run_room', { run_id: testRunId });
        // Initial UI state update based on data passed from template
        updateButtonStates(initialStatus);
        // Update progress UI with data potentially passed from the template if the page reloaded mid-run
        const initialProgress = parseInt(progressBar.getAttribute('aria-valuenow') || "0");
        const initialCurrent = parseInt(testRunDataElement.dataset.runProgressCurrent || "0");
        const initialTotal = parseInt(testRunDataElement.dataset.runProgressTotal || "0");
        updateProgressUI({
            status: initialStatus,
            percent: initialProgress,
            current: initialCurrent,
            total: initialTotal,
            name: testRunDataElement.dataset.runName || "Test Run" // Get name if available
        });
    });

    socket.on('disconnect', (reason) => {
        console.log(`Socket.IO disconnected: ${reason}`);
        if (reason === 'io server disconnect') {
            // The server deliberately disconnected the client
            socket.connect(); // Optionally try to reconnect
        }
        // else the socket will automatically try to reconnect
        statusElement.textContent = 'Disconnected. Attempting to reconnect...';
        // Disable all control buttons on disconnect
        if (pauseButton) pauseButton.disabled = true;
        if (resumeButton) resumeButton.disabled = true;
        if (cancelButton) cancelButton.disabled = true;
    });

    socket.on('connect_error', (error) => {
        console.error('Socket.IO connection error:', error);
        statusElement.textContent = 'Connection Error. Refresh to try again.';
        // Disable all control buttons on connection error
        if (pauseButton) pauseButton.disabled = true;
        if (resumeButton) resumeButton.disabled = true;
        if (cancelButton) cancelButton.disabled = true;
    });

    // --- Listen for Server Emitted Events ---

    socket.on('progress_update', (data) => {
        // console.log('Socket.IO received progress_update:', data);
        if (data.run_id == testRunId) { // Ensure update is for this run
            initialStatus = data.status; // Update current known status
            updateProgressUI(data);
            updateButtonStates(data.status);
        }
    });

    socket.on('run_pausing', (data) => {
        console.log('Socket.IO received run_pausing:', data);
        if (data.run_id == testRunId) {
            initialStatus = 'pausing';
            updateProgressUI(data);
            updateButtonStates('pausing');
            statusElement.textContent = 'Pausing...';
        }
    });

    socket.on('run_paused', (data) => {
        console.log('Socket.IO received run_paused:', data);
        if (data.run_id == testRunId) {
            initialStatus = 'paused';
            updateProgressUI(data);
            updateButtonStates('paused');
            statusElement.textContent = 'Paused';
        }
    });

    socket.on('run_resuming', (data) => {
        console.log('Socket.IO received run_resuming:', data);
        if (data.run_id == testRunId) {
            initialStatus = 'running'; // Assume it transitions to running
            updateProgressUI(data);
            updateButtonStates('running');
            statusElement.textContent = 'Running';
        }
    });

    socket.on('run_cancelling', (data) => {
        console.log('Socket.IO received run_cancelling:', data);
        if (data.run_id == testRunId) {
            initialStatus = 'cancelling';
            updateProgressUI(data); // Update progress bar with current state
            updateButtonStates('cancelling');
            statusElement.textContent = 'Cancelling...';
        }
    });

    socket.on('run_cancelled', (data) => {
        console.log('Socket.IO received run_cancelled:', data);
        if (data.run_id == testRunId) {
            initialStatus = 'cancelled';
            updateProgressUI(data);
            updateButtonStates('cancelled');
            statusElement.textContent = 'Cancelled';
        }
    });

    socket.on('run_completed', (data) => {
        console.log('Socket.IO received run_completed:', data);
        if (data.run_id == testRunId) {
            initialStatus = 'completed';
            updateProgressUI(data); // Should show 100%
            updateButtonStates('completed');
            statusElement.textContent = 'Completed';
            // Optionally, you might want to reload the page or part of it
            // to show final results clearly if they aren't dynamically updated.
            // For now, we just update status.
        }
    });

    socket.on('run_failed', (data) => {
        console.log('Socket.IO received run_failed:', data);
        if (data.run_id == testRunId) {
            initialStatus = 'failed';
            updateProgressUI(data);
            updateButtonStates('failed');
            statusElement.textContent = 'Failed';
        }
    });

    socket.on('error_event', (data) => {
        console.error('Socket.IO server error_event:', data.message);
        // Display a user-friendly message, perhaps using a flash message system if you have one client-side
        alert(`Server Error: ${data.message}`); // Simple alert for now
    });

    socket.on('execution_result_update', data => {
        // Remove the old activity indicator - no more "[... Case X ...]" messages
        
        const row = document.getElementById(`exec-${data.execution_id}`);
        if (row) {
          // Update status cell
          row.dataset.status = data.status;
          row.querySelector('select[name=status]').value = data.status;
      
          // Update response JSON
          const codeBlock = row.querySelector('.json-response');
          codeBlock.textContent = JSON.stringify(data.response_data, null, 2);
      
          // Optionally, highlight the row
          row.classList.add(data.status === 'passed' ? 'bg-green-50'
                         : data.status === 'failed' ? 'bg-red-50'
                         : '');
        }

        // Increment the donut chart slice
        if (window.cumulativeChart) {
            const ds = window.cumulativeChart.data.datasets[0].data;
            if (data.status === 'passed')       ds[0] += 1;
            else if (data.status === 'failed')  ds[1] += 1;
            else if (data.status === 'skipped') ds[2] += 1;
            else if (data.status === 'pending_review') ds[3] += 1;
            window.cumulativeChart.update();
        }
        });

    // New handler for HTTP status code statistics
    socket.on('status_code_update', data => {
        if (data.run_id == testRunId) {
            updateStatusCodeStats(data);
        }
    });
            


    // --- Client Emitted Event Handlers (Button Clicks) ---
    if (pauseButton) {
        pauseButton.addEventListener('click', () => {
            if (socket.connected) {
                console.log(`Emitting 'request_pause_run' for TestRun ID: ${testRunId}`);
                socket.emit('request_pause_run', { run_id: testRunId });
                // Optimistic UI update (server will confirm with 'run_pausing' or 'run_paused')
                updateButtonStates('pausing');
                statusElement.textContent = 'Pausing...';
            } else {
                alert('Not connected to server. Please check your connection.');
            }
        });
    }

    if (resumeButton) {
        resumeButton.addEventListener('click', () => {
            if (socket.connected) {
                console.log(`Emitting 'request_resume_run' for TestRun ID: ${testRunId}`);
                socket.emit('request_resume_run', { run_id: testRunId });
                // Optimistic UI update
                updateButtonStates('running'); // Assuming it will go to running
                statusElement.textContent = 'Resuming...';
            } else {
                alert('Not connected to server. Please check your connection.');
            }
        });
    }

    if (cancelButton) {
        cancelButton.addEventListener('click', () => {
            if (confirm('Are you sure you want to cancel this test run?')) {
                if (socket.connected) {
                    console.log(`Emitting 'request_cancel_run' for TestRun ID: ${testRunId}`);
                    socket.emit('request_cancel_run', { run_id: testRunId });
                    // Optimistic UI update
                    updateButtonStates('cancelling');
                    statusElement.textContent = 'Cancelling...';
                } else {
                    alert('Not connected to server. Please check your connection.');
                }
            }
        });
    }

    // --- UI Update Functions ---
    function updateProgressUI(data) {
        const status = data.status || initialStatus; // Fallback to initialStatus if not in data
        const current = parseInt(data.current || "0");
        const total = parseInt(data.total || "0");
        let percent = parseInt(data.percent || "0");

        // Ensure progress bar container is visible if relevant
        if (progressSection) {
            if (['pending', 'running', 'pausing', 'paused', 'cancelling', 'completed', 'failed', 'cancelled'].includes(status) && total >= 0) {
                progressSection.style.display = 'block';
            } else if (status === 'not_started') {
                progressSection.style.display = 'none';
            }
        }
        
        percent = Math.min(Math.max(percent, 0), 100); // Cap percentage

        if (statusElement) statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        if (progressBar) {
            progressBar.style.width = percent + '%';
            progressBar.setAttribute('aria-valuenow', percent);
        }
        if (progressBarText) progressBarText.textContent = percent + '%';
        
        if (progressCounter) {
            if (total > 0 || current > 0) { // Show counter if there's any progress or total
                progressCounter.textContent = `${current} / ${total} cases processed`;
            } else if (status === 'pending') {
                progressCounter.textContent = 'Execution pending...';
            } else if (status === 'not_started') {
                progressCounter.textContent = 'Not started.';
            } else {
                progressCounter.textContent = ''; // Clear if no relevant info
            }
        }

        // Style progress bar based on status
        if (progressBar) {
            progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-success', 'bg-danger', 'bg-warning', 'bg-info', 'bg-secondary');
            if (['running', 'pending', 'resuming'].includes(status)) {
                progressBar.classList.add('progress-bar-animated', 'progress-bar-striped', 'bg-info');
            } else if (['pausing', 'paused'].includes(status)) {
                progressBar.classList.add('bg-warning');
                if (status === 'pausing') progressBar.classList.add('progress-bar-animated', 'progress-bar-striped');
            } else if (status === 'cancelling') {
                progressBar.classList.add('progress-bar-animated', 'progress-bar-striped', 'bg-warning');
            } else if (status === 'completed') {
                progressBar.classList.add('bg-success');
            } else if (status === 'failed') {
                progressBar.classList.add('bg-danger');
            } else if (status === 'cancelled') {
                progressBar.classList.add('bg-secondary'); // Or bg-warning
            }
        }
    }      

    function updateButtonStates(status) {
        // Hide all control buttons by default, then show based on status
        if (pauseButton) pauseButton.style.display = 'none';
        if (resumeButton) resumeButton.style.display = 'none';
        if (cancelButton) cancelButton.style.display = 'none';
        if (startButton) startButton.disabled = false; // Enable by default

        if (status === 'running') {
            if (pauseButton) pauseButton.style.display = 'inline-block';
            if (cancelButton) cancelButton.style.display = 'inline-block';
            if (startButton) startButton.disabled = true;
        } else if (status === 'paused') {
            if (resumeButton) resumeButton.style.display = 'inline-block';
            if (cancelButton) cancelButton.style.display = 'inline-block';
            if (startButton) startButton.disabled = true;
        } else if (status === 'pending' || status === 'pausing' || status === 'cancelling') {
            // Typically, only cancel is available during these transient states from client-side
            if (cancelButton) cancelButton.style.display = 'inline-block';
            if (startButton) startButton.disabled = true;
        } else if (status === 'completed' || status === 'failed' || status === 'cancelled' || status === 'not_started') {
            // No ongoing actions possible, Start button is primary
            if (startButton) startButton.disabled = false;
        }
    }

    function updateStatusCodeStats(data) {
        const statusCodeSection = document.getElementById('status-code-section');
        const status2xx = document.getElementById('status-2xx');
        const status4xx = document.getElementById('status-4xx');
        const status5xx = document.getElementById('status-5xx');
        const statusOther = document.getElementById('status-other');
        const statusOtherGroup = document.getElementById('status-other-group');
        const detailedStatusCodes = document.getElementById('detailed-status-codes');

        if (!statusCodeSection || !status2xx || !status4xx || !status5xx || !statusOther || !detailedStatusCodes) {
            console.warn('Status code UI elements not found');
            return;
        }

        // Show the section if there are any requests
        if (data.total_requests > 0) {
            statusCodeSection.style.display = 'block';
        }

        // Update group counts
        status2xx.textContent = data.status_groups['2xx'] || 0;
        status4xx.textContent = data.status_groups['4xx'] || 0;
        status5xx.textContent = data.status_groups['5xx'] || 0;
        statusOther.textContent = data.status_groups['other'] || 0;

        // Show/hide "Other" group if it has values
        if ((data.status_groups['other'] || 0) > 0) {
            statusOtherGroup.style.display = 'block';
        } else {
            statusOtherGroup.style.display = 'none';
        }

        // Update detailed breakdown
        const detailedText = Object.entries(data.detailed_counts)
            .sort(([a], [b]) => parseInt(a) - parseInt(b))
            .map(([code, count]) => `${code}: ${count}`)
            .join(' | ');
        detailedStatusCodes.textContent = detailedText || 'No HTTP requests yet';

        // Add visual warning for high error rates
        const errorRate = ((data.status_groups['4xx'] || 0) + (data.status_groups['5xx'] || 0)) / data.total_requests;
        if (errorRate > 0.5 && data.total_requests > 10) {
            statusCodeSection.style.borderColor = '#ff6b6b';
            statusCodeSection.style.backgroundColor = 'rgba(255, 107, 107, 0.1)';
        } else {
            statusCodeSection.style.borderColor = '';
            statusCodeSection.style.backgroundColor = '';
        }
    }

    // --- On Page Unload ---
    window.addEventListener('beforeunload', () => {
        if (socket && socket.connected) {
            console.log(`Emitting 'leave_test_run_room' before unload for TestRun ID: ${testRunId}`);
            socket.emit('leave_test_run_room', { run_id: testRunId });
            socket.disconnect(); // Cleanly disconnect the socket
        }
    });

}); // End DOMContentLoaded