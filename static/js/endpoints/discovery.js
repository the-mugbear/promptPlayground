// Global variables for UI elements
let loadingOverlay;
let discoverButtonText;
let discoverySpinner;
let discoveryResults;
let endpointsList;
let statusDiv;
let statusText;
let progressBar;
let discoveryProgress;

let currentTaskId = null;
let pollInterval = null;

// Function to reset loading state
function resetLoadingState() {
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
        loadingOverlay.classList.remove('flex');
    }
    if (discoverButtonText) {
        discoverButtonText.textContent = 'Discover Endpoints';
    }
    if (discoverySpinner) {
        discoverySpinner.classList.add('hidden');
    }
    if (statusDiv) {
        statusDiv.classList.add('hidden');
    }
    if (progressBar) {
        progressBar.style.width = '0%';
    }
    if (discoveryProgress) {
        discoveryProgress.classList.add('hidden');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize global variables
    loadingOverlay = document.getElementById('loadingOverlay');
    discoverButtonText = document.getElementById('discoverButtonText');
    discoverySpinner = document.getElementById('discoverySpinner');
    discoveryResults = document.getElementById('discoveryResults');
    endpointsList = document.getElementById('endpointsList');
    const discoveryForm = document.getElementById('discoveryForm');
    const discoverBtn = document.getElementById('discoverBtn');
    const discoveryModal = document.getElementById('discoveryModal');
    const closeModal = document.getElementById('closeModal');
    const discoveryStrategy = document.getElementById('discoveryStrategy');
    discoveryProgress = document.getElementById('discoveryProgress');
    statusDiv = document.getElementById('discoveryStatus');
    statusText = document.getElementById('statusText');
    progressBar = document.getElementById('progressBar');

    // Only set up modal-related event listeners if the elements exist
    if (discoverBtn && discoveryModal) {
        discoverBtn.addEventListener('click', async () => {
            const baseUrl = document.getElementById('baseUrl').value;
            const strategy = discoveryStrategy ? discoveryStrategy.value : 'auto';
            const apiKey = document.getElementById('apiKey')?.value;

            if (!baseUrl) {
                alert('Please enter a base URL');
                return;
            }

            if (discoveryProgress) discoveryProgress.classList.remove('hidden');
            if (discoveryResults) discoveryResults.innerHTML = '';

            try {
                const response = await fetch('/endpoints/discover', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        base_url: baseUrl,
                        strategy: strategy,
                        api_key: apiKey
                    })
                });

                const data = await response.json();

                if (response.ok && data.task_id) {
                    pollTaskStatus(data.task_id);
                } else {
                    if (discoveryResults) {
                        discoveryResults.innerHTML = `
                            <div class="text-red-600">
                                ${data.error || 'Failed to start endpoint discovery'}
                            </div>
                        `;
                    }
                    if (discoveryProgress) discoveryProgress.classList.add('hidden');
                }
            } catch (error) {
                console.error('Error:', error);
                if (discoveryResults) {
                    discoveryResults.innerHTML = `
                        <div class="text-red-600">
                            Error: ${error.message}
                        </div>
                    `;
                }
                if (discoveryProgress) discoveryProgress.classList.add('hidden');
            }
        });
    }

    if (closeModal) {
        closeModal.addEventListener('click', () => {
            if (discoveryModal) discoveryModal.classList.add('hidden');
        });
    }

    // Handle discovery form submission if the form exists
    if (discoveryForm) {
        discoveryForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const baseUrl = document.getElementById('baseUrl').value.trim();
            const apiKey = document.getElementById('apiKey').value.trim();
            
            if (!baseUrl) {
                alert('Please enter a base URL');
                return;
            }

            showLoading();
            updateStatus('Starting discovery...', 5);

            try {
                const response = await fetch('/endpoints/discover', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        base_url: baseUrl,
                        api_key: apiKey
                    })
                });

                const data = await response.json();
                
                if (data.error) {
                    hideLoading();
                    updateStatus('Error: ' + data.error, 0);
                    alert('Error: ' + data.error);
                    return;
                }

                if (data.task_id) {
                    currentTaskId = data.task_id;
                    pollTaskStatus(data.task_id);
                }
            } catch (error) {
                console.error('Discovery error:', error);
                hideLoading();
                updateStatus('Error starting discovery', 0);
                alert('Error starting discovery: ' + error.message);
            }
        });
    }

    // Handle strategy-based discovery if the strategy selector exists
    if (discoveryStrategy) {
        discoveryStrategy.addEventListener('change', async (e) => {
            const strategy = e.target.value;
            const endpointId = document.querySelector('.endpoint-details')?.dataset?.endpointId;
            
            if (!endpointId) return;
            
            if (discoveryProgress) discoveryProgress.classList.remove('hidden');
            if (discoveryResults) discoveryResults.innerHTML = '';
            
            try {
                const response = await fetch(`/endpoints/${endpointId}/discover`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        strategy: strategy
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    // Start polling for task status
                    pollTaskStatus(data.task_id);
                } else {
                    if (discoveryResults) {
                        discoveryResults.innerHTML = `
                            <div class="text-red-600">
                                ${data.error || 'Failed to start endpoint discovery'}
                            </div>
                        `;
                    }
                    if (discoveryProgress) discoveryProgress.classList.add('hidden');
                }
            } catch (error) {
                if (discoveryResults) {
                    discoveryResults.innerHTML = `
                        <div class="text-red-600">
                            Error starting endpoint discovery: ${error.message}
                        </div>
                    `;
                }
                if (discoveryProgress) discoveryProgress.classList.add('hidden');
            }
        });
    }
});

// Function to poll task status
async function pollTaskStatus(taskId) {
    try {
        const response = await fetch(`/endpoints/discovery/status/${taskId}`);
        const data = await response.json();

        if (data.state === 'PENDING') {
            // Continue polling
            setTimeout(() => pollTaskStatus(taskId), 1000);
        } else if (data.state === 'SUCCESS') {
            if (discoveryProgress) discoveryProgress.classList.add('hidden');
            if (discoveryResults) {
                const endpoints = Array.isArray(data.status) ? data.status : [];
                if (endpoints.length > 0) {
                    discoveryResults.innerHTML = `
                        <div class="text-green-600 mb-4">Found ${endpoints.length} endpoints:</div>
                        <div class="space-y-2">
                            ${endpoints.map(endpoint => `
                                <div class="p-2 bg-gray-100 rounded">
                                    <div class="font-mono">${endpoint.method} ${endpoint.url}</div>
                                    ${endpoint.status_code ? `<div class="text-sm text-gray-600">Status: ${endpoint.status_code}</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    `;
                } else {
                    discoveryResults.innerHTML = `
                        <div class="text-yellow-600">
                            No endpoints discovered. Try a different strategy or check the base URL.
                        </div>
                    `;
                }
            }
        } else if (data.state === 'FAILURE') {
            if (discoveryProgress) discoveryProgress.classList.add('hidden');
            if (discoveryResults) {
                discoveryResults.innerHTML = `
                    <div class="text-red-600">
                        Discovery failed: ${data.status}
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error polling task status:', error);
        if (discoveryProgress) discoveryProgress.classList.add('hidden');
        if (discoveryResults) {
            discoveryResults.innerHTML = `
                <div class="text-red-600">
                    Error checking task status: ${error.message}
                </div>
            `;
        }
    }
}

// Function to display discovery results
function displayResults(endpoints) {
    if (!endpointsList || !discoveryResults) {
        console.error('Required DOM elements not found');
        return;
    }

    console.log('Displaying results:', endpoints); // Debug log

    endpointsList.innerHTML = '';
    discoveryResults.classList.remove('hidden');

    if (!endpoints || !Array.isArray(endpoints) || endpoints.length === 0) {
        endpointsList.innerHTML = `
            <div class="text-purple-300 bg-gray-800/50 p-4 rounded-lg">
                No endpoints discovered. Try a different base URL or strategy.
            </div>
        `;
        return;
    }

    endpoints.forEach(endpoint => {
        if (!endpoint.url || !endpoint.method) {
            console.warn('Invalid endpoint data:', endpoint);
            return;
        }

        const endpointElement = document.createElement('div');
        endpointElement.className = 'bg-gray-800/50 p-4 rounded-lg border border-purple-500/30 hover:border-purple-500/50 transition-colors duration-200';
        endpointElement.innerHTML = `
            <div class="flex justify-between items-start">
                <div>
                    <h4 class="text-purple-300 font-medium">${endpoint.url}</h4>
                    <p class="text-purple-200 text-sm mt-1">Method: ${endpoint.method}</p>
                </div>
                <button onclick="addEndpoint('${endpoint.url}', '${endpoint.method}')" 
                        class="px-3 py-1 text-sm bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-md transition-all duration-200">
                    Add Endpoint
                </button>
            </div>
        `;
        endpointsList.appendChild(endpointElement);
    });
}

// Function to add a discovered endpoint
async function addEndpoint(url, method) {
    try {
        const response = await fetch('/endpoints', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                method: method
            })
        });

        if (response.ok) {
            window.location.reload();
        } else {
            const data = await response.json();
            throw new Error(data.error || 'Failed to add endpoint');
        }
    } catch (error) {
        console.error('Add endpoint error:', error);
        alert('Failed to add endpoint: ' + error.message);
    }
}

function showLoading() {
    discoverButtonText.textContent = 'Discovering...';
    discoverySpinner.classList.remove('hidden');
    statusDiv.classList.remove('hidden');
    loadingOverlay.classList.remove('hidden');
    loadingOverlay.classList.add('flex');
    discoveryResults.classList.add('hidden');
    progressBar.style.width = '0%';
}

function hideLoading() {
    discoverButtonText.textContent = 'Discover Endpoints';
    discoverySpinner.classList.add('hidden');
    statusDiv.classList.add('hidden');
    loadingOverlay.classList.add('hidden');
    loadingOverlay.classList.remove('flex');
}

function updateStatus(message, progress) {
    statusText.textContent = message;
    if (progress !== undefined) {
        progressBar.style.width = `${progress}%`;
    }
} 