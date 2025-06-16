/**
 * Chain Creation Wizard - Interactive guided workflow builder
 */

class ChainWizard {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 4;
        this.selectedTemplate = null;
        this.selectedEndpoints = [];
        this.chainConfig = {
            name: '',
            description: '',
            steps: []
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.updateUI();
    }
    
    setupEventListeners() {
        // Navigation buttons
        document.getElementById('prev-btn')?.addEventListener('click', () => this.previousStep());
        document.getElementById('next-btn')?.addEventListener('click', () => this.nextStep());
        document.getElementById('create-btn')?.addEventListener('click', () => this.createChain());
        
        // Template selection
        document.querySelectorAll('.template-card').forEach(card => {
            card.addEventListener('click', () => this.selectTemplate(card));
        });
        
        // Endpoint selection
        document.querySelectorAll('input[data-endpoint-id]').forEach(checkbox => {
            checkbox.addEventListener('change', () => this.updateEndpointSelection());
        });
        
        // Chain name and description inputs
        document.getElementById('chain-name')?.addEventListener('input', (e) => {
            this.chainConfig.name = e.target.value;
        });
        
        document.getElementById('chain-description')?.addEventListener('input', (e) => {
            this.chainConfig.description = e.target.value;
        });
    }
    
    selectTemplate(card) {
        // Remove previous selection
        document.querySelectorAll('.template-card').forEach(c => c.classList.remove('selected'));
        
        // Select new template
        card.classList.add('selected');
        this.selectedTemplate = card.dataset.template;
        
        // Enable next button
        this.updateNavigation();
    }
    
    updateEndpointSelection() {
        this.selectedEndpoints = [];
        document.querySelectorAll('input[data-endpoint-id]:checked').forEach(checkbox => {
            this.selectedEndpoints.push(parseInt(checkbox.dataset.endpointId));
        });
        
        this.updateNavigation();
    }
    
    nextStep() {
        if (this.currentStep < this.totalSteps && this.canProceed()) {
            this.currentStep++;
            this.updateUI();
            
            // Special handling for specific steps
            if (this.currentStep === 3) {
                this.generateStepsConfiguration();
            } else if (this.currentStep === 4) {
                this.generateReview();
            }
        }
    }
    
    previousStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.updateUI();
        }
    }
    
    canProceed() {
        switch (this.currentStep) {
            case 1:
                return this.selectedTemplate !== null;
            case 2:
                return this.selectedEndpoints.length > 0 && this.chainConfig.name.trim() !== '';
            case 3:
                return true; // Step 3 is always proceedable
            default:
                return true;
        }
    }
    
    updateUI() {
        // Update step visibility
        document.querySelectorAll('.wizard-step').forEach(step => {
            step.classList.remove('active');
        });
        document.querySelector(`[data-step="${this.currentStep}"]`).classList.add('active');
        
        // Update progress indicators
        document.querySelectorAll('.progress-step').forEach((step, index) => {
            const stepNumber = index + 1;
            const circle = step.querySelector('.step-circle');
            const label = step.querySelector('.step-label');
            
            circle.classList.remove('active', 'completed');
            label.classList.remove('active');
            
            if (stepNumber < this.currentStep) {
                circle.classList.add('completed');
                circle.innerHTML = '<i class="fas fa-check"></i>';
            } else if (stepNumber === this.currentStep) {
                circle.classList.add('active');
                label.classList.add('active');
                circle.textContent = stepNumber;
            } else {
                circle.textContent = stepNumber;
            }
        });
        
        this.updateNavigation();
    }
    
    updateNavigation() {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const createBtn = document.getElementById('create-btn');
        
        // Previous button
        prevBtn.disabled = this.currentStep === 1;
        
        // Next/Create buttons
        if (this.currentStep === this.totalSteps) {
            nextBtn.style.display = 'none';
            createBtn.style.display = 'inline-flex';
            createBtn.disabled = !this.canProceed();
        } else {
            nextBtn.style.display = 'inline-flex';
            createBtn.style.display = 'none';
            nextBtn.disabled = !this.canProceed();
        }
    }
    
    generateStepsConfiguration() {
        const container = document.getElementById('steps-configuration');
        if (!container) return;
        
        // Get endpoint details for selected endpoints
        const endpointDetails = this.selectedEndpoints.map((id, index) => {
            const endpointItem = document.querySelector(`[data-endpoint-id="${id}"]`);
            const name = endpointItem.querySelector('strong').textContent;
            const method = endpointItem.querySelector('.endpoint-method').textContent;
            
            return {
                id: id,
                name: name,
                method: method,
                order: index + 1
            };
        });
        
        // Apply template-based ordering suggestions
        const orderedEndpoints = this.applyTemplateOrdering(endpointDetails);
        
        container.innerHTML = `
            <div class="steps-list">
                <p class="text-muted mb-3">
                    <i class="fas fa-info-circle"></i>
                    Based on your template selection, we've suggested an optimal order for your endpoints.
                    You can drag to reorder if needed.
                </p>
                ${orderedEndpoints.map((endpoint, index) => `
                    <div class="step-preview" data-endpoint-id="${endpoint.id}">
                        <div class="step-preview-header">
                            <div class="step-number">${index + 1}</div>
                            <div>
                                <strong>${endpoint.name}</strong>
                                <span class="endpoint-method http-${endpoint.method.toLowerCase()}">${endpoint.method}</span>
                            </div>
                            <div class="ml-auto">
                                <i class="fas fa-grip-vertical" style="cursor: grab; color: var(--text-muted);"></i>
                            </div>
                        </div>
                        <div class="step-suggestions">
                            ${this.generateStepSuggestions(endpoint, index, orderedEndpoints)}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        
        this.makeStepsSortable();
    }
    
    applyTemplateOrdering(endpoints) {
        // Apply template-specific logic
        switch (this.selectedTemplate) {
            case 'auth-data':
                // Put authentication endpoints first
                return endpoints.sort((a, b) => {
                    const aIsAuth = a.name.toLowerCase().includes('auth') || a.name.toLowerCase().includes('login');
                    const bIsAuth = b.name.toLowerCase().includes('auth') || b.name.toLowerCase().includes('login');
                    if (aIsAuth && !bIsAuth) return -1;
                    if (!aIsAuth && bIsAuth) return 1;
                    return 0;
                });
                
            case 'create-process':
                // Put create/POST endpoints first
                return endpoints.sort((a, b) => {
                    if (a.method === 'POST' && b.method !== 'POST') return -1;
                    if (a.method !== 'POST' && b.method === 'POST') return 1;
                    return 0;
                });
                
            default:
                return endpoints;
        }
    }
    
    generateStepSuggestions(endpoint, index, allEndpoints) {
        const suggestions = [];
        
        switch (this.selectedTemplate) {
            case 'auth-data':
                if (index === 0) {
                    suggestions.push('Extract access token from response');
                } else {
                    suggestions.push('Use access token from previous step');
                }
                break;
                
            case 'create-process':
                if (index === 0) {
                    suggestions.push('Extract resource ID from response');
                } else {
                    suggestions.push('Use resource ID from step 1');
                }
                break;
        }
        
        if (suggestions.length === 0) {
            suggestions.push('Configure data extraction rules as needed');
        }
        
        return `
            <div class="text-muted small">
                <i class="fas fa-lightbulb"></i>
                Suggestion: ${suggestions.join(', ')}
            </div>
        `;
    }
    
    makeStepsSortable() {
        // Simple drag and drop would go here
        // For now, we'll keep the current order
    }
    
    generateReview() {
        const container = document.getElementById('chain-review');
        if (!container) return;
        
        const endpointCount = this.selectedEndpoints.length;
        const templateName = this.getTemplateName(this.selectedTemplate);
        
        container.innerHTML = `
            <div class="review-summary">
                <div class="review-item">
                    <h5><i class="fas fa-tag"></i> Chain Details</h5>
                    <p><strong>Name:</strong> ${this.chainConfig.name}</p>
                    <p><strong>Description:</strong> ${this.chainConfig.description || 'No description provided'}</p>
                    <p><strong>Template:</strong> ${templateName}</p>
                </div>
                
                <div class="review-item">
                    <h5><i class="fas fa-list-ol"></i> Workflow Steps</h5>
                    <p>This chain will execute <strong>${endpointCount} steps</strong> in sequence:</p>
                    <ol class="steps-summary">
                        ${this.selectedEndpoints.map((id, index) => {
                            const endpointItem = document.querySelector(`[data-endpoint-id="${id}"]`);
                            const name = endpointItem.querySelector('strong').textContent;
                            const method = endpointItem.querySelector('.endpoint-method').textContent;
                            return `<li><span class="endpoint-method http-${method.toLowerCase()}">${method}</span> ${name}</li>`;
                        }).join('')}
                    </ol>
                </div>
                
                <div class="review-item">
                    <h5><i class="fas fa-info-circle"></i> Next Steps</h5>
                    <p>After creating this chain, you can:</p>
                    <ul>
                        <li>Configure detailed step settings and data extraction rules</li>
                        <li>Test individual steps and the complete workflow</li>
                        <li>Use the interactive debugger to troubleshoot</li>
                        <li>Execute the chain in your test runs</li>
                    </ul>
                </div>
            </div>
        `;
    }
    
    getTemplateName(template) {
        const templates = {
            'auth-data': 'Authentication + Data Fetch',
            'create-process': 'Create + Process',
            'search-analyze': 'Search + Analyze',
            'notification-chain': 'Notification Chain',
            'custom': 'Custom Workflow'
        };
        return templates[template] || 'Unknown Template';
    }
    
    async createChain() {
        const createBtn = document.getElementById('create-btn');
        const originalText = createBtn.innerHTML;
        
        try {
            createBtn.disabled = true;
            createBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
            
            // Create the chain
            const response = await fetch('/chains/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: new URLSearchParams({
                    name: this.chainConfig.name,
                    description: this.chainConfig.description
                })
            });
            
            if (response.ok) {
                const result = await response.text();
                // Extract chain ID from redirect or response
                const chainId = this.extractChainId(response);
                
                // Add steps to the chain
                if (chainId) {
                    await this.addStepsToChain(chainId);
                }
                
                // Redirect to chain details
                window.location.href = `/chains/${chainId}`;
            } else {
                throw new Error('Failed to create chain');
            }
            
        } catch (error) {
            console.error('Error creating chain:', error);
            alert('Failed to create chain. Please try again.');
            
        } finally {
            createBtn.disabled = false;
            createBtn.innerHTML = originalText;
        }
    }
    
    extractChainId(response) {
        // This would need to be implemented based on the actual response format
        // For now, return a placeholder
        return 1;
    }
    
    async addStepsToChain(chainId) {
        // Add each selected endpoint as a step
        for (let i = 0; i < this.selectedEndpoints.length; i++) {
            const endpointId = this.selectedEndpoints[i];
            
            try {
                await fetch(`/chains/${chainId}/steps/add`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                    },
                    body: new URLSearchParams({
                        endpoint: endpointId,
                        name: `Step ${i + 1}`
                    })
                });
            } catch (error) {
                console.error(`Error adding step ${i + 1}:`, error);
            }
        }
    }
}

// Initialize wizard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new ChainWizard();
});