/**
 * Handles inline editing of endpoint fields with confirmation dialogs
 */
class InlineEditor {
  constructor() {
    this.endpointId = document.querySelector('.endpoint-details')?.dataset.endpointId;
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Make fields editable on click
    document.querySelectorAll('.editable-field .view-mode span').forEach(span => {
      span.addEventListener('click', () => this.startEditing(span));
    });

    // Handle input changes
    document.querySelectorAll('.editable-field input, .editable-field textarea').forEach(input => {
      input.addEventListener('blur', () => this.handleFieldChange(input));
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          input.blur();
        }
      });
    });

    // Handle header editing
    this.setupHeaderEditing();
  }

  startEditing(span) {
    const field = span.closest('.editable-field');
    const input = field.querySelector('input, textarea');
    field.classList.add('editing');
    input.value = span.textContent.trim();
    input.focus();
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
        alert('Failed to update field. Please try again.');
      }
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
          <p><strong>${fieldName}</strong></p>
          <p><span class="old-value">${this.escapeHtml(oldValue)}</span></p>
          <p><span class="new-value">${this.escapeHtml(newValue)}</span></p>
        </div>
        <div class="buttons">
          <button class="cancel-btn">Cancel</button>
          <button class="confirm-btn">Confirm Change</button>
        </div>
      `;

      overlay.appendChild(dialog);
      document.body.appendChild(overlay);

      dialog.querySelector('.cancel-btn').addEventListener('click', () => {
        document.body.removeChild(overlay);
        resolve(false);
      });

      dialog.querySelector('.confirm-btn').addEventListener('click', () => {
        document.body.removeChild(overlay);
        resolve(true);
      });
    });
  }

  async updateField(fieldName, value) {
    const response = await fetch(`/endpoints/${this.endpointId}/update_field`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({ [fieldName]: value })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `Failed to update ${fieldName}`);
    }

    return response.json();
  }

  setupHeaderEditing() {
    const headersBox = document.querySelector('.headers-box');
    if (!headersBox) return;

    // Add header button
    const addHeader = document.createElement('div');
    addHeader.className = 'add-header';
    addHeader.textContent = '+ Add Header';
    addHeader.addEventListener('click', () => this.addNewHeader());
    headersBox.appendChild(addHeader);

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
      <button class="edit-btn">Edit</button>
      <button class="delete-btn">Delete</button>
    `;

    headerItem.appendChild(actions);

    actions.querySelector('.edit-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      const oldKey = keySpan.textContent.replace(':', '').trim();
      const oldValue = valueSpan.textContent.trim();
      
      // Create a modal dialog for editing
      const modal = document.createElement('div');
      modal.className = 'header-edit-modal';
      modal.innerHTML = `
        <div class="modal-content">
          <h3>Edit Header</h3>
          <div class="form-group">
            <label>Key:</label>
            <input type="text" id="header-key-input" value="${this.escapeHtml(oldKey)}">
          </div>
          <div class="form-group">
            <label>Value:</label>
            <textarea id="header-value-input">${this.escapeHtml(oldValue)}</textarea>
          </div>
          <div class="modal-actions">
            <button class="cancel-btn">Cancel</button>
            <button class="save-btn">Save</button>
          </div>
        </div>
      `;

      document.body.appendChild(modal);

      // Function to remove modal
      const removeModal = () => {
        if (document.body.contains(modal)) {
          document.body.removeChild(modal);
        }
      };

      // Handle save
      modal.querySelector('.save-btn').addEventListener('click', async () => {
        const newKey = modal.querySelector('#header-key-input').value.trim();
        const newValue = modal.querySelector('#header-value-input').value.trim();
        
        if (!newKey) {
          alert('Header key cannot be empty');
          return;
        }

        // Remove the edit modal first
        removeModal();

        const confirmed = await this.showConfirmationDialog(
          'Header',
          `${oldKey}: ${oldValue}`,
          `${newKey}: ${newValue}`
        );

        if (confirmed) {
          try {
            await this.updateHeader(oldKey, newKey, newValue);
            keySpan.textContent = newKey + ':';
            valueSpan.textContent = newValue;
          } catch (error) {
            console.error('Failed to update header:', error);
            alert('Failed to update header. Please try again.');
          }
        }
      });

      // Handle cancel
      modal.querySelector('.cancel-btn').addEventListener('click', removeModal);

      // Handle clicking outside the modal
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          removeModal();
        }
      });

      // Handle escape key
      const handleEscape = (e) => {
        if (e.key === 'Escape') {
          removeModal();
          document.removeEventListener('keydown', handleEscape);
        }
      };
      document.addEventListener('keydown', handleEscape);
    });

    actions.querySelector('.delete-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      const key = keySpan.textContent.replace(':', '').trim();
      const value = valueSpan.textContent.trim();

      const confirmed = await this.showConfirmationDialog(
        'Delete Header',
        `${key}: ${value}`,
        'Delete this header'
      );

      if (confirmed) {
        try {
          await this.deleteHeader(key);
          headerItem.remove();
        } catch (error) {
          console.error('Failed to delete header:', error);
          alert('Failed to delete header. Please try again.');
        }
      }
    });
  }

  async addNewHeader() {
    // Create a modal dialog for adding
    const modal = document.createElement('div');
    modal.className = 'header-edit-modal';
    modal.innerHTML = `
      <div class="modal-content">
        <h3>Add Header</h3>
        <div class="form-group">
          <label>Key:</label>
          <input type="text" id="header-key-input">
        </div>
        <div class="form-group">
          <label>Value:</label>
          <textarea id="header-value-input"></textarea>
        </div>
        <div class="modal-actions">
          <button class="cancel-btn">Cancel</button>
          <button class="save-btn">Save</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // Function to remove modal
    const removeModal = () => {
      if (document.body.contains(modal)) {
        document.body.removeChild(modal);
      }
    };

    // Handle save
    modal.querySelector('.save-btn').addEventListener('click', async () => {
      const key = modal.querySelector('#header-key-input').value.trim();
      const value = modal.querySelector('#header-value-input').value.trim();
      
      if (!key) {
        alert('Header key cannot be empty');
        return;
      }

      try {
        await this.updateHeader('', key, value);
        
        const headersBox = document.querySelector('.headers-box');
        const headerItem = document.createElement('div');
        headerItem.className = 'header-item';
        headerItem.innerHTML = `
          <span class="header-key">${this.escapeHtml(key)}:</span>
          <span class="header-value">${this.escapeHtml(value)}</span>
        `;
        
        this.makeHeaderEditable(headerItem);
        headersBox.insertBefore(headerItem, headersBox.lastElementChild);
        removeModal();
      } catch (error) {
        console.error('Failed to add header:', error);
        alert('Failed to add header. Please try again.');
      }
    });

    // Handle cancel
    modal.querySelector('.cancel-btn').addEventListener('click', removeModal);

    // Handle clicking outside the modal
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        removeModal();
      }
    });

    // Handle escape key
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        removeModal();
        document.removeEventListener('keydown', handleEscape);
      }
    };
    document.addEventListener('keydown', handleEscape);
  }

  async updateHeader(oldKey, newKey, newValue) {
    console.log('Updating header:', { oldKey, newKey, newValue });
    try {
      const response = await fetch(`/endpoints/${this.endpointId}/update_header`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
          old_key: oldKey,
          new_key: newKey,
          new_value: newValue
        })
      });

      console.log('Response status:', response.status);
      const data = await response.json();
      console.log('Response data:', data);

      if (!response.ok) {
        throw new Error(data.error || 'Failed to update header');
      }

      return data;
    } catch (error) {
      console.error('Error updating header:', error);
      throw error;
    }
  }

  async deleteHeader(key) {
    console.log('Deleting header:', key);
    try {
      const response = await fetch(`/endpoints/${this.endpointId}/delete_header`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ key })
      });

      console.log('Response status:', response.status);
      const data = await response.json();
      console.log('Response data:', data);

      if (!response.ok) {
        throw new Error(data.error || 'Failed to delete header');
      }

      return data;
    } catch (error) {
      console.error('Error deleting header:', error);
      throw error;
    }
  }

  escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Initialize the inline editor when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new InlineEditor();
}); 