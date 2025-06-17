// endpointDetails.js
document.addEventListener("DOMContentLoaded", function() {
    const endpointSelect = document.getElementById('endpoint_id');
    if (endpointSelect) {

      endpointSelect.addEventListener('change', async function(e) {
        const endpointId = e.target.value;
        if (!endpointId) return;
        try {
          const resp = await fetch(`/endpoints/${endpointId}/json`, {
            headers: {
              'X-CSRFToken': csrfToken // Add CSRF token to headers
            }
          });
          const data = await resp.json();
          // populate payload
          const payloadTextarea = document.getElementById('endpointPayload');
          if (payloadTextarea) {
            payloadTextarea.value = data.http_payload || '';
          }
          // populate headers
          const headersContainer = document.getElementById('headersContainer');
          if (headersContainer) {
            headersContainer.innerHTML = '';
            (data.headers || []).forEach(hdr => {
              const row = document.createElement('div');
              row.classList.add('header-row');
              row.innerHTML = `
                <input type="text" class="header-key" name="header_key" value="${hdr.key}">
                <input type="text" class="header-value" name="header_value" value="${hdr.value}">
              `;
              headersContainer.appendChild(row);
            });
          }

          // Populate header overrides section
          populateHeaderOverrides(data.headers || []);
        } catch (err) {
          console.error("Failed to load endpoint:", err);
          alert("Error loading endpoint data. See console for details.");
        }
      });
    }
  });

  // Header override functionality
  function populateHeaderOverrides(headers) {
    const endpointHeadersSection = document.getElementById('endpoint-headers-section');
    const noEndpointSelected = document.getElementById('no-endpoint-selected');
    const currentHeadersDisplay = document.getElementById('current-headers-display');
    const jwtWarnings = document.getElementById('jwt-warnings');

    if (!endpointHeadersSection) return;

    // Show/hide sections
    endpointHeadersSection.style.display = 'block';
    noEndpointSelected.style.display = 'none';

    // Display current headers
    currentHeadersDisplay.innerHTML = '';
    if (headers.length === 0) {
      currentHeadersDisplay.innerHTML = '<div class="text-muted">No headers configured for this endpoint</div>';
    } else {
      headers.forEach(header => {
        const headerDiv = document.createElement('div');
        headerDiv.className = 'header-item';
        headerDiv.innerHTML = `
          <span class="header-key">${escapeHtml(header.key)}:</span>
          <span class="header-value">${escapeHtml(header.value)}</span>
        `;
        currentHeadersDisplay.appendChild(headerDiv);
      });
    }

    // Analyze JWT tokens and show warnings
    analyzeAuthHeaders(headers);
  }

  function analyzeAuthHeaders(headers) {
    const jwtWarnings = document.getElementById('jwt-warnings');
    if (!jwtWarnings) return;

    jwtWarnings.innerHTML = '';

    headers.forEach(header => {
      if (header.key.toLowerCase() === 'authorization' && header.value.startsWith('Bearer ')) {
        const token = header.value.substring(7);
        const analysis = analyzeJWTToken(token);
        
        if (analysis.warning) {
          const warningDiv = document.createElement('div');
          warningDiv.className = `jwt-warning ${analysis.isExpired ? 'expired' : ''}`;
          warningDiv.innerHTML = `
            <i class="fas fa-${analysis.isExpired ? 'exclamation-triangle' : 'clock'}"></i>
            <span><strong>${header.key}:</strong> ${analysis.warning}</span>
          `;
          jwtWarnings.appendChild(warningDiv);
        }
      }
    });
  }

  function analyzeJWTToken(token) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return { warning: null, isExpired: false };

      // Decode payload
      const payload = parts[1];
      const paddedPayload = payload + '='.repeat((4 - payload.length % 4) % 4);
      const decodedPayload = JSON.parse(atob(paddedPayload));

      if (!decodedPayload.exp) return { warning: null, isExpired: false };

      const expDate = new Date(decodedPayload.exp * 1000);
      const now = new Date();
      const isExpired = now >= expDate;

      let warning;
      if (isExpired) {
        const timeDiff = now - expDate;
        const daysDiff = Math.floor(timeDiff / (1000 * 60 * 60 * 24));
        const hoursDiff = Math.floor(timeDiff / (1000 * 60 * 60));
        
        if (daysDiff > 0) {
          warning = `Token expired ${daysDiff} day${daysDiff > 1 ? 's' : ''} ago`;
        } else if (hoursDiff > 0) {
          warning = `Token expired ${hoursDiff} hour${hoursDiff > 1 ? 's' : ''} ago`;
        } else {
          warning = 'Token expired recently';
        }
      } else {
        const timeDiff = expDate - now;
        const daysDiff = Math.floor(timeDiff / (1000 * 60 * 60 * 24));
        const hoursDiff = Math.floor(timeDiff / (1000 * 60 * 60));
        const minutesDiff = Math.floor(timeDiff / (1000 * 60));

        if (daysDiff > 1) {
          warning = `Token expires in ${daysDiff} days`;
        } else if (hoursDiff > 0) {
          warning = `Token expires in ${hoursDiff} hour${hoursDiff > 1 ? 's' : ''}`;
        } else if (minutesDiff > 5) {
          warning = `Token expires in ${minutesDiff} minutes`;
        } else {
          warning = 'Token expires very soon!';
        }
      }

      return { warning, isExpired };
    } catch (e) {
      return { warning: null, isExpired: false };
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Header override row management
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('add-header-btn') || e.target.closest('.add-header-btn')) {
      addHeaderOverrideRow();
    } else if (e.target.classList.contains('remove-header-btn') || e.target.closest('.remove-header-btn')) {
      removeHeaderOverrideRow(e.target.closest('.header-override-row'));
    }
  });

  function addHeaderOverrideRow() {
    const container = document.getElementById('header-overrides-container');
    const newRow = document.createElement('div');
    newRow.className = 'header-override-row';
    newRow.innerHTML = `
      <input type="text" class="form-control header-key" placeholder="Header Name (e.g., Authorization)" style="width: 30%;" name="override_key">
      <input type="text" class="form-control header-value" placeholder="Header Value (e.g., Bearer new-token)" style="width: 60%;" name="override_value">
      <button type="button" class="btn btn-sm btn-danger remove-header-btn" style="width: 8%;">
        <i class="fas fa-minus"></i>
      </button>
    `;
    container.appendChild(newRow);
  }

  function removeHeaderOverrideRow(row) {
    row.remove();
  }
  