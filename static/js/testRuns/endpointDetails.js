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
        } catch (err) {
          console.error("Failed to load endpoint:", err);
          alert("Error loading endpoint data. See console for details.");
        }
      });
    }
  });
  