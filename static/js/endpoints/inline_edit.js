/**
 * Handles inline editing of endpoint fields with confirmation dialogs
 */
class InlineEditor {
  constructor() {
    const endpointDetails = document.querySelector('.endpoint-details');
    console.log('Found endpoint details element:', endpointDetails);
    this.endpointId = endpointDetails?.dataset.endpointId;
    console.log('Endpoint ID:', this.endpointId);
    this.setupEventListeners();
  }

  isJWT(token) {
    // Remove 'Bearer ' prefix if present
    if (token.startsWith('Bearer ')) {
      token = token.substring(7);
    }
    
    // Check if token matches JWT format (three base64-encoded parts separated by dots)
    const jwtRegex = /^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$/;
    console.log('Checking if token is JWT:', token);
    console.log('Token matches regex:', jwtRegex.test(token));
    return jwtRegex.test(token);
  }

  decodeJWT(token) {
    try {
      console.log('Attempting to decode JWT:', token);
      // Remove 'Bearer ' prefix if present
      if (token.startsWith('Bearer ')) {
        token = token.substring(7);
        console.log('Removed Bearer prefix:', token);
      }

      // Split the token into parts
      const parts = token.split('.');
      console.log('Token parts:', parts);
      if (parts.length !== 3) {
        console.log('Invalid token parts length:', parts.length);
        return null;
      }

      try {
        // Decode the payload (second part)
        const payload = JSON.parse(atob(parts[1]));
        console.log('Decoded payload:', payload);
        return payload;
      } catch (e) {
        console.error('Error decoding payload:', e);
        return null;
      }
    } catch (e) {
      console.error('Error decoding JWT:', e);
      return null;
    }
  }

  getTokenExpirationInfo(token) {
    console.log('Getting token expiration info for:', token);
    if (!this.isJWT(token)) {
      console.log('Token is not a valid JWT');
      return null;
    }

    const payload = this.decodeJWT(token);
    console.log('Decoded payload:', payload);
    if (!payload || !payload.exp) {
      console.log('No payload or expiration time found');
      return null;
    }

    const now = Math.floor(Date.now() / 1000);
    const expiresAt = payload.exp;
    const timeRemaining = expiresAt - now;
    console.log('Time remaining:', timeRemaining);

    if (timeRemaining <= 0) {
      console.log('Token has expired');
      return {
        isExpired: true,
        message: 'Token has expired'
      };
    }

    // Format the remaining time
    const days = Math.floor(timeRemaining / (24 * 60 * 60));
    const hours = Math.floor((timeRemaining % (24 * 60 * 60)) / (60 * 60));
    const minutes = Math.floor((timeRemaining % (60 * 60)) / 60);

    let message = '';
    if (days > 0) message += `${days} day${days !== 1 ? 's' : ''} `;
    if (hours > 0) message += `${hours} hour${hours !== 1 ? 's' : ''} `;
    if (minutes > 0) message += `${minutes} minute${minutes !== 1 ? 's' : ''}`;

    console.log('Token expires in:', message.trim());
    return {
      isExpired: false,
      message: `Expires in ${message.trim()}`
    };
  }

  updateTokenExpirationInfo(headerItem) {
    console.log('Updating token info for header item:', headerItem);
    const valueSpan = headerItem.querySelector('.header-value');
    const tokenInfo = headerItem.querySelector('.token-info');
    
    console.log('Value span:', valueSpan);
    console.log('Current value:', valueSpan?.textContent);
    
    // Remove existing token info if any
    if (tokenInfo) {
      console.log('Removing existing token info');
      tokenInfo.remove();
    }

    const value = valueSpan.textContent.trim();
    console.log('Trimmed value:', value);
    
    if (value.toLowerCase().startsWith('bearer ')) {
      console.log('Value starts with Bearer, checking JWT');
      const expirationInfo = this.getTokenExpirationInfo(value);
      console.log('Expiration info:', expirationInfo);
      
      if (expirationInfo) {
        console.log('Creating token info span');
        const infoSpan = document.createElement('span');
        infoSpan.className = `token-info ${expirationInfo.isExpired ? 'expired' : 'valid'}`;
        infoSpan.textContent = expirationInfo.message;
        
        // Insert before the actions div
        const actions = headerItem.querySelector('.header-actions');
        console.log('Actions div:', actions);
        
        if (actions) {
          console.log('Inserting before actions');
          headerItem.insertBefore(infoSpan, actions);
        } else {
          console.log('Appending to header item');
          headerItem.appendChild(infoSpan);
        }
      }
    }
  }

  setupEventListeners() {
    // Make fields editable on click
    document.querySelectorAll('.editable-field .view-mode span').forEach(span => {
      span.addEventListener('click', () => this.startEditing(span));
    });

    // Handle input changes by selecting input, textarea, AND select elements
    document.querySelectorAll('.editable-field input, .editable-field textarea, .editable-field select').forEach(input => {
      // 'blur' works for all elements and is a good generic event to trigger a save
      input.addEventListener('blur', () => this.handleFieldChange(input));
      
      // For a better user experience, we can also save immediately on 'change' for the dropdown
      if (input.tagName === 'SELECT') {
        input.addEventListener('change', () => this.handleFieldChange(input));
      }

      // This keydown listener is mostly for text inputs but won't harm the select element
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && input.tagName !== 'TEXTAREA') {
          e.preventDefault();
          input.blur(); // Trigger blur to save the change
        }
      });
    });

    // Handle header editing
    this.setupHeaderEditing();
  }

  startEditing(span) {
    const field = span.closest('.editable-field');
    const input = field.querySelector('input, textarea, select');
    field.classList.add('editing');
    input.value = span.textContent.trim();
    input.focus();
    if (input.select) { // Select text in input for easy replacement
        input.select();
    }
  }

  async handleFieldChange(input) {
    const field = input.closest('.editable-field');
    const viewMode = field.querySelector('.view-mode span');
    const oldValue = viewMode.textContent.trim();
    const newValue = input.value.trim();

    if (oldValue === newValue) {
      field.classList.remove('editing');
      return;
    }

    const confirmed = await this.showConfirmationDialog(
      field.querySelector('label').textContent,
      oldValue,
      newValue
    );

    if (confirmed) {
      try {
        await this.updateField(field.dataset.field, newValue);
        viewMode.textContent = newValue;
      } catch (error) {
        console.error('Failed to update field:', error);
        alert(`Failed to update field: ${error.message}`); // Show error message from server if available
      }
    } else {
        // If not confirmed, revert input to old value if needed, or just remove editing class
        // viewMode.textContent = oldValue; // Not strictly necessary as DOM wasn't updated yet
    }

    field.classList.remove('editing');
  }

  async showConfirmationDialog(fieldName, oldValue, newValue) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'dialog-overlay';

      const dialog = document.createElement('div');
      dialog.className = 'confirmation-dialog';
      dialog.innerHTML = `
        <h3>Confirm Change</h3>
        <div class="changes">
          <p><strong>${this.escapeHtml(fieldName)}</strong></p>
          <p>From: <span class="old-value">${this.escapeHtml(oldValue)}</span></p>
          <p>To: <span class="new-value">${this.escapeHtml(newValue)}</span></p>
        </div>
        <div class="buttons">
          <button class="cancel-btn">Cancel</button>
          <button class="confirm-btn">Confirm Change</button>
        </div>
      `;

      overlay.appendChild(dialog);
      document.body.appendChild(overlay);

      const confirmBtn = dialog.querySelector('.confirm-btn');
      const cancelBtn = dialog.querySelector('.cancel-btn');

      const closeDialog = (confirmedStatus) => {
        document.body.removeChild(overlay);
        resolve(confirmedStatus);
      };
      
      confirmBtn.addEventListener('click', () => closeDialog(true));
      cancelBtn.addEventListener('click', () => closeDialog(false));
      overlay.addEventListener('click', (e) => { // Close on overlay click
        if (e.target === overlay) {
            closeDialog(false);
        }
      });
      document.addEventListener('keydown', function escapeListener(e) { // Close on Escape key
        if (e.key === 'Escape') {
            closeDialog(false);
            document.removeEventListener('keydown', escapeListener);
        }
      });
      confirmBtn.focus(); // Focus the confirm button by default
    });
  }

  async updateField(fieldName, value) {
    const response = await fetch(`/endpoints/${this.endpointId}/update_field`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken  // Add CSRF token
      },
      body: JSON.stringify({ [fieldName]: value })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Unknown error during field update.' }));
      throw new Error(errorData.error || `Failed to update ${fieldName}`);
    }

    return response.json().catch(() => ({})); // Return empty object if no JSON body on success
  }

  setupHeaderEditing() {
    const headersBox = document.querySelector('.headers-box');
    if (!headersBox) return;

    // Add header button
    const addHeaderBtn = document.createElement('div');
    addHeaderBtn.className = 'add-header';
    addHeaderBtn.textContent = '+ Add Header';
    addHeaderBtn.addEventListener('click', () => this.addNewHeader());
    headersBox.appendChild(addHeaderBtn); // Append it after existing headers might be better UX

    // Make existing headers editable
    headersBox.querySelectorAll('.header-item').forEach(item => {
      this.makeHeaderEditable(item);
    });
  }

  makeHeaderEditable(headerItem) {
    const keySpan = headerItem.querySelector('.header-key');
    const valueSpan = headerItem.querySelector('.header-value');
    const actions = document.createElement('div');
    actions.className = 'header-actions';
    actions.innerHTML = `
      <button class="edit-btn" title="Edit Header">Edit</button>
      <button class="delete-btn" title="Delete Header">Delete</button>
    `;

    headerItem.appendChild(actions);

    // Check for JWT token in existing header
    this.updateTokenExpirationInfo(headerItem);

    actions.querySelector('.edit-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      const oldKey = keySpan.textContent.replace(':', '').trim();
      const oldValue = valueSpan.textContent.trim();
      
      // Create a modal dialog for editing
      const modal = document.createElement('div');
      modal.className = 'header-edit-modal dialog-overlay'; // Use dialog-overlay for consistent styling
      modal.innerHTML = `
        <div class="modal-content confirmation-dialog">
          <h3>Edit Header</h3>
          <div class="form-group">
            <label for="header-key-input">Key:</label>
            <input type="text" id="header-key-input" value="${this.escapeHtml(oldKey)}">
          </div>
          <div class="form-group">
            <label for="header-value-input">Value:</label>
            <textarea id="header-value-input">${this.escapeHtml(oldValue)}</textarea>
          </div>
          <div class="modal-actions buttons">
            <button class="cancel-btn">Cancel</button>
            <button class="save-btn confirm-btn">Save</button>
          </div>
        </div>
      `;

      document.body.appendChild(modal);
      const keyInput = modal.querySelector('#header-key-input');
      keyInput.focus();
      keyInput.select();


      // Function to remove modal
      const removeModal = () => {
        if (document.body.contains(modal)) {
          document.body.removeChild(modal);
          document.removeEventListener('keydown', handleEscape);
        }
      };
      
      const handleEscape = (e) => {
        if (e.key === 'Escape') {
          removeModal();
        }
      };
      document.addEventListener('keydown', handleEscape);


      // Handle save
      modal.querySelector('.save-btn').addEventListener('click', async () => {
        const newKey = modal.querySelector('#header-key-input').value.trim();
        const newValue = modal.querySelector('#header-value-input').value.trim();
        
        if (!newKey) {
          alert('Header key cannot be empty');
          return;
        }

        removeModal(); // Remove edit modal before showing confirmation

        const confirmed = await this.showConfirmationDialog(
          'Header Update',
          `${oldKey}: ${oldValue}`,
          `${newKey}: ${newValue}`
        );

        if (confirmed) {
          try {
            await this.handleHeaderEdit(headerItem, newKey, newValue);
          } catch (error) {
            console.error('Failed to update header:', error);
            alert(`Failed to update header: ${error.message}`);
          }
        }
      });

      // Handle cancel
      modal.querySelector('.cancel-btn').addEventListener('click', removeModal);
      modal.addEventListener('click', (e) => { // Close on overlay click
        if (e.target === modal) {
            removeModal();
        }
      });
    });

    actions.querySelector('.delete-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      const key = keySpan.textContent.replace(':', '').trim();
      const value = valueSpan.textContent.trim();
      // *** MODIFICATION: Get headerId from dataset ***
      const headerId = headerItem.dataset.headerId;

      if (!headerId) {
        alert('Error: Header ID not found for deletion.');
        console.error('Header ID missing from dataset:', headerItem);
        return;
      }

      const confirmed = await this.showConfirmationDialog(
        'Delete Header',
        `${key}: ${value}`,
        'Delete this header?' // More explicit confirmation message
      );

      if (confirmed) {
        try {
          // *** MODIFICATION: Pass headerId to deleteHeader ***
          await this.deleteHeader(headerId); 
          headerItem.remove();
        } catch (error) {
          console.error('Failed to delete header:', error);
          alert(`Failed to delete header: ${error.message}`);
        }
      }
    });
  }

  async addNewHeader() {
    // Create a modal dialog for adding
    const modal = document.createElement('div');
    modal.className = 'header-edit-modal dialog-overlay'; // Use dialog-overlay
    modal.innerHTML = `
      <div class="modal-content confirmation-dialog">
        <h3>Add Header</h3>
        <div class="form-group">
          <label for="header-key-input">Key:</label>
          <input type="text" id="header-key-input">
        </div>
        <div class="form-group">
          <label for="header-value-input">Value:</label>
          <textarea id="header-value-input"></textarea>
        </div>
        <div class="modal-actions buttons">
          <button class="cancel-btn">Cancel</button>
          <button class="save-btn confirm-btn">Save</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    const keyInput = modal.querySelector('#header-key-input');
    keyInput.focus();


    // Function to remove modal
    const removeModal = () => {
      if (document.body.contains(modal)) {
        document.body.removeChild(modal);
        document.removeEventListener('keydown', handleEscape);
      }
    };
    
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        removeModal();
      }
    };
    document.addEventListener('keydown', handleEscape);


    // Handle save
    modal.querySelector('.save-btn').addEventListener('click', async () => {
      const key = modal.querySelector('#header-key-input').value.trim();
      const value = modal.querySelector('#header-value-input').value.trim();
      
      if (!key) {
        alert('Header key cannot be empty');
        return;
      }

      try {
        const requestData = {
          key: key,
          value: value
        };
        console.log('Sending request data for new header:', requestData);
        
        // *** MODIFICATION: Updated URL for creating header ***
        const response = await fetch(`/endpoints/${this.endpointId}/headers`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify(requestData)
        });

        console.log('Create header response status:', response.status);
        console.log('Create header response headers:', Object.fromEntries(response.headers.entries()));
        
        const responseText = await response.text();
        console.log('Raw response text from create header:', responseText);
        
        let data;
        try {
          data = JSON.parse(responseText);
        } catch (parseError) {
          console.error('Failed to parse response JSON from create header:', parseError);
          throw new Error(`Invalid JSON response from server: ${responseText.substring(0, 100)}`); // Show snippet
        }
        
        if (!response.ok) {
          throw new Error(data.error || 'Failed to create header');
        }

        const headersBox = document.querySelector('.headers-box');
        const addHeaderButton = headersBox.querySelector('.add-header'); // Find the add button
        const headerItem = document.createElement('div');
        headerItem.className = 'header-item';
        // *** MODIFICATION: Ensure data.header and data.header.id exist ***
        if (data.header && data.header.id) {
            headerItem.dataset.headerId = data.header.id;
        } else {
            console.error("Header ID missing in response from server:", data);
            alert("Error: Could not get header ID from server. Header may not function correctly for edits/deletes.");
        }
        headerItem.innerHTML = `
          <span class="header-key">${this.escapeHtml(key)}:</span>
          <span class="header-value">${this.escapeHtml(value)}</span>
        `;
        
        this.makeHeaderEditable(headerItem);
        // Insert before the "Add Header" button for better UX
        if (addHeaderButton) {
            headersBox.insertBefore(headerItem, addHeaderButton);
        } else {
            headersBox.appendChild(headerItem); // Fallback
        }

        // Check for JWT token in new header value
        this.updateTokenExpirationInfo(headerItem);
        removeModal();
      } catch (error) {
        console.error('Failed to add header:', error);
        alert(`Failed to add header: ${error.message}`);
      }
    });

    // Handle cancel
    modal.querySelector('.cancel-btn').addEventListener('click', removeModal);
    modal.addEventListener('click', (e) => { // Close on overlay click
      if (e.target === modal) {
          removeModal();
      }
    });
  }

  async handleHeaderEdit(headerItem, key, value) {
    try {
      const headerId = headerItem.dataset.headerId;
      if (!headerId) {
        alert("Error: Cannot update header without an ID.");
        return;
      }
      await this.updateHeader(headerId, key, value);
      const keySpan = headerItem.querySelector('.header-key');
      const valueSpan = headerItem.querySelector('.header-value');
      keySpan.textContent = this.escapeHtml(key) + ':';
      valueSpan.textContent = this.escapeHtml(value);
      // Update token info after editing
      this.updateTokenExpirationInfo(headerItem);
    } catch (error) {
      console.error('Failed to update header (in handleHeaderEdit):', error);
      // Alert is handled in updateHeader, or re-throw if specific handling is needed here
      // alert('Failed to update header. Please try again.');
      throw error; // Re-throw so the caller knows it failed
    }
  }

  async updateHeader(headerId, newKey, newValue) {
    console.log('Updating header:', { headerId, newKey, newValue });
    try {
      const response = await fetch(`/endpoints/${this.endpointId}/headers/${headerId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          key: newKey,
          value: newValue
        })
      });

      console.log('Update header response status:', response.status);
      const data = await response.json().catch(() => ({ error: 'Unknown error during header update or invalid JSON response.' }));
      console.log('Update header response data:', data);

      if (!response.ok) {
        throw new Error(data.error || 'Failed to update header');
      }

      return data;
    } catch (error) {
      console.error('Error updating header:', error);
      throw error;
    }
  }

  // *** MODIFICATION: Parameter changed from key to headerId ***
  async deleteHeader(headerId) { 
    console.log('Deleting header with ID:', headerId);
    try {
      const response = await fetch(`/endpoints/${this.endpointId}/headers/${headerId}`, {
        method: 'DELETE',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken
        }
      });

      console.log('Delete header response status:', response.status);
      let data = {};
      // For DELETE, a 204 No Content is a common successful response and will have no body.
      // Other success statuses like 200 or 202 might have a body.
      if (response.status !== 204 && response.headers.get("content-length") !== "0") {
          try {
            data = await response.json();
          } catch (e) {
            console.warn("Could not parse JSON from delete response, but status was ok (not 204). Status:", response.status, e);
            // If response.ok is true but body is not JSON, it might be fine.
          }
      }
      console.log('Delete header response data:', data);

      if (!response.ok) {
        // Try to get error from data if it exists, otherwise a generic message
        throw new Error(data.error || `Failed to delete header (status: ${response.status})`);
      }

      return data; // Or true if no meaningful data is returned on success
    } catch (error) {
      console.error('Error deleting header:', error);
      throw error;
    }
  }

  escapeHtml(str) {
    if (typeof str !== 'string') {
        if (str === null || str === undefined) return '';
        str = String(str);
    }
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Initialize the inline editor when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  if (document.querySelector('.endpoint-details')) { // Only init if on the right page
    new InlineEditor();
  }
});