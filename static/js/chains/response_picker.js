/**
 * Response Data Picker - Interactive UI for selecting data from API responses
 * to create data extraction rules for chain steps
 */

class ResponseDataPicker {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.responseData = null;
        this.selectedPaths = [];
        this.onSelectionChange = null;
        
        this.init();
    }
    
    init() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="response-picker">
                <div class="picker-header">
                    <h4><i class="fas fa-mouse-pointer"></i> Response Data Picker</h4>
                    <p class="text-muted">Click on values in the response to extract them as variables</p>
                    <div class="picker-status" id="picker-status" style="display: none;">
                        <i class="fas fa-check-circle"></i> <span id="status-text"></span>
                    </div>
                </div>
                <div class="picker-body">
                    <div class="response-display" id="response-json-display">
                        <div class="empty-state">
                            <i class="fas fa-flask"></i>
                            <p>Test your step to see the response data</p>
                        </div>
                    </div>
                    <div class="extraction-rules" id="extraction-rules-display">
                        <h5><i class="fas fa-list"></i> Extraction Rules Preview</h5>
                        <div class="rules-list" id="rules-list"></div>
                        <button type="button" class="btn btn-sm btn-secondary" id="clear-selections">
                            <i class="fas fa-trash"></i> Clear All
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        document.getElementById('clear-selections')?.addEventListener('click', () => {
            this.clearSelections();
        });
    }
    
    setResponseData(data) {
        this.responseData = data;
        this.renderResponse();
    }
    
    renderResponse() {
        const display = document.getElementById('response-json-display');
        if (!display || !this.responseData) return;
        
        // Check if it's already a string (non-JSON response)
        if (typeof this.responseData === 'string') {
            try {
                // Try to parse as JSON first
                const parsed = JSON.parse(this.responseData);
                display.innerHTML = `<div class="json-formatted">${this.createInteractiveJson(parsed, [], 0)}</div>`;
            } catch (e) {
                // If not JSON, display as plain text with basic formatting
                display.innerHTML = `
                    <div class="plain-text-response">
                        <div class="response-type-indicator">
                            <i class="fas fa-file-text"></i> Plain Text Response
                        </div>
                        <pre class="clickable-value" data-path="response_text" data-type="string" title="Path: response_text">${this.escapeHtml(this.responseData)}</pre>
                    </div>
                `;
            }
        } else {
            // It's already an object
            display.innerHTML = `<div class="json-formatted">${this.createInteractiveJson(this.responseData, [], 0)}</div>`;
        }
        
        // Add click listeners after rendering
        this.addClickListeners();
    }
    
    createInteractiveJson(obj, path = [], depth = 0) {
        const indent = '  '.repeat(depth);
        const pathStr = path.length > 0 ? path.join('.') : 'root';
        
        if (obj === null) {
            return `<span class="json-null clickable-value" data-path="${pathStr}" data-type="null" title="Path: ${pathStr}">null</span>`;
        }
        
        if (typeof obj === 'boolean') {
            return `<span class="json-boolean clickable-value" data-path="${pathStr}" data-type="boolean" title="Path: ${pathStr}">${obj}</span>`;
        }
        
        if (typeof obj === 'number') {
            return `<span class="json-number clickable-value" data-path="${pathStr}" data-type="number" title="Path: ${pathStr}">${obj}</span>`;
        }
        
        if (typeof obj === 'string') {
            return `<span class="json-string clickable-value" data-path="${pathStr}" data-type="string" title="Path: ${pathStr}">"${this.escapeHtml(obj)}"</span>`;
        }
        
        if (Array.isArray(obj)) {
            if (obj.length === 0) {
                return '<span class="json-bracket">[]</span>';
            }
            
            let html = '<span class="json-bracket">[</span>\n';
            obj.forEach((item, index) => {
                const currentPath = [...path, index];
                html += `<div class="json-line" style="margin-left: ${(depth + 1) * 1}rem;">`;
                html += this.createInteractiveJson(item, currentPath, depth + 1);
                if (index < obj.length - 1) html += '<span class="json-comma">,</span>';
                html += `</div>`;
            });
            html += `\n<span class="json-bracket" style="margin-left: ${depth * 1}rem;">]</span>`;
            return html;
        }
        
        if (typeof obj === 'object') {
            const keys = Object.keys(obj);
            if (keys.length === 0) {
                return '<span class="json-bracket">{}</span>';
            }
            
            // For objects with many keys, make them collapsible
            const isLarge = keys.length > 5;
            const containerId = `obj-${Math.random().toString(36).substr(2, 9)}`;
            
            let html = '<span class="json-bracket">{</span>';
            
            if (isLarge) {
                html += `<span class="collapse-toggle" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'; this.textContent = this.textContent === ' [−] ' ? ' [+] ' : ' [−] ';"> [−] </span>`;
                html += `<div class="collapsible-content" id="${containerId}">`;
            } else {
                html += '\n';
            }
            
            keys.forEach((key, index) => {
                const currentPath = [...path, key];
                const currentPathStr = currentPath.join('.');
                html += `<div class="json-line" style="margin-left: ${(depth + 1) * 1}rem;">`;
                html += `<span class="json-key clickable-value" data-path="${currentPathStr}" data-type="key" title="Path: ${currentPathStr}">"${this.escapeHtml(key)}"</span>`;
                html += '<span class="json-colon">: </span>';
                html += this.createInteractiveJson(obj[key], currentPath, depth + 1);
                if (index < keys.length - 1) html += '<span class="json-comma">,</span>';
                html += `</div>`;
            });
            
            if (isLarge) {
                html += `</div>`;
            }
            
            html += `\n<span class="json-bracket" style="margin-left: ${depth * 1}rem;">}</span>`;
            return html;
        }
        
        return String(obj);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    addClickListeners() {
        const clickableElements = this.container.querySelectorAll('.clickable-value');
        clickableElements.forEach(element => {
            element.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleValueClick(element);
            });
        });
    }
    
    handleValueClick(element) {
        const path = element.dataset.path;
        const type = element.dataset.type;
        
        console.log('Clicked element:', { 
            path, 
            type, 
            element, 
            textContent: element.textContent.substring(0, 50) + '...',
            generatedVariableName: this.generateVariableName(path)
        }); // Enhanced debug log
        
        if (this.selectedPaths.some(selection => selection.path === path)) {
            // Remove if already selected
            this.selectedPaths = this.selectedPaths.filter(selection => selection.path !== path);
            element.classList.remove('selected');
            console.log('Removed selection for path:', path);
        } else {
            // Add new selection
            const variableName = this.generateVariableName(path);
            const selection = {
                path: path,
                type: type,
                variableName: variableName,
                element: element
            };
            this.selectedPaths.push(selection);
            element.classList.add('selected');
            console.log('Added selection:', selection);
        }
        
        this.updateExtractionRules();
        this.updateFormField(); // Make sure form field is updated
        
        if (this.onSelectionChange) {
            this.onSelectionChange(this.selectedPaths);
        }
    }
    
    updateFormField() {
        // Update the data extraction rules textarea directly
        const extractionRulesTextarea = document.getElementById('data_extraction_rules');
        if (extractionRulesTextarea) {
            const existingRules = this.parseExistingRules(extractionRulesTextarea.value);
            const newRules = this.getExtractionRulesJson();
            
            // Merge existing rules with new selections (avoid duplicates)
            const allRules = [...existingRules];
            newRules.forEach(newRule => {
                if (!existingRules.some(existing => existing.source_identifier === newRule.source_identifier)) {
                    allRules.push(newRule);
                }
            });
            
            extractionRulesTextarea.value = JSON.stringify(allRules, null, 2);
            
            // Add visual feedback
            extractionRulesTextarea.style.backgroundColor = 'rgba(0, 255, 65, 0.1)';
            setTimeout(() => {
                extractionRulesTextarea.style.backgroundColor = '';
            }, 500);
            
            console.log('Updated extraction rules:', allRules); // Debug log
            
            // Show status message
            this.showStatus(`Added ${newRules.length} extraction rule(s)`);
        }
    }
    
    showStatus(message) {
        const statusElement = document.getElementById('picker-status');
        const statusText = document.getElementById('status-text');
        if (statusElement && statusText) {
            statusText.textContent = message;
            statusElement.style.display = 'block';
            statusElement.style.color = 'var(--accent-color, #00ff41)';
            
            setTimeout(() => {
                statusElement.style.display = 'none';
            }, 2000);
        }
    }
    
    parseExistingRules(rulesText) {
        try {
            const parsed = JSON.parse(rulesText || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }
    
    generateVariableName(path) {
        if (!path || path === 'root') return 'response_body';
        
        // Handle special case for plain text responses
        if (path === 'response_text') return 'response_text';
        
        // Convert path like "user.profile.name" to "user_profile_name"
        const parts = path.split('.').filter(part => part !== '' && part !== 'root');
        
        if (parts.length === 0) return 'response_body';
        
        // Take the last meaningful part as the primary name
        let name = parts[parts.length - 1];
        
        // If it's just a number (array index), use the parent + item
        if (/^\d+$/.test(name) && parts.length > 1) {
            name = parts[parts.length - 2] + '_item';
        }
        
        // If it's still just a number, use full path
        if (/^\d+$/.test(name)) {
            name = parts.join('_');
        }
        
        // Clean up the name
        name = name.toLowerCase();
        name = name.replace(/[^a-z0-9_]/g, '_');
        name = name.replace(/_{2,}/g, '_');
        name = name.replace(/^_|_$/g, '');
        
        // If name starts with a number, prefix it
        if (/^\d/.test(name)) {
            name = 'item_' + name;
        }
        
        return name || 'extracted_value';
    }
    
    updateExtractionRules() {
        const rulesList = document.getElementById('rules-list');
        if (!rulesList) return;
        
        if (this.selectedPaths.length === 0) {
            rulesList.innerHTML = '<div class="empty-rules">No data selected</div>';
            return;
        }
        
        rulesList.innerHTML = this.selectedPaths.map((selection, index) => `
            <div class="rule-item">
                <div class="rule-header">
                    <input type="text" class="variable-name-input" value="${selection.variableName}" 
                           data-index="${index}" placeholder="Variable name">
                    <button type="button" class="btn btn-sm btn-danger remove-rule" data-index="${index}">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="rule-path">
                    <span class="path-label">Path:</span>
                    <code>${selection.path}</code>
                </div>
            </div>
        `).join('');
        
        this.setupRuleEventListeners();
    }
    
    setupRuleEventListeners() {
        // Variable name input changes
        document.querySelectorAll('.variable-name-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const index = parseInt(e.target.dataset.index);
                this.selectedPaths[index].variableName = e.target.value;
                if (this.onSelectionChange) {
                    this.onSelectionChange(this.selectedPaths);
                }
            });
        });
        
        // Remove rule buttons
        document.querySelectorAll('.remove-rule').forEach(button => {
            button.addEventListener('click', (e) => {
                const index = parseInt(e.target.dataset.index);
                const selection = this.selectedPaths[index];
                selection.element.classList.remove('selected');
                this.selectedPaths.splice(index, 1);
                this.updateExtractionRules();
                if (this.onSelectionChange) {
                    this.onSelectionChange(this.selectedPaths);
                }
            });
        });
    }
    
    clearSelections() {
        this.selectedPaths.forEach(selection => {
            selection.element.classList.remove('selected');
        });
        this.selectedPaths = [];
        this.updateExtractionRules();
        if (this.onSelectionChange) {
            this.onSelectionChange(this.selectedPaths);
        }
    }
    
    getExtractionRulesJson() {
        return this.selectedPaths.map(selection => ({
            variable_name: selection.variableName,
            source_type: "json_body",
            source_identifier: selection.path
        }));
    }
}

// Export for use in other files
window.ResponseDataPicker = ResponseDataPicker;