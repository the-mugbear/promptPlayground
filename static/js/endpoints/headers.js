
// We'll keep an array in JS to track the parsed headers
let headerEntries = [];

/**
 * Parses the multiline 'raw_headers' textarea into {key, value} objects,
 * then renders them in the right-panel for editing.
 */
function parseHeaders() {
    const rawText = document.getElementById('raw_headers').value;
    const lines = rawText.split('\n');
    headerEntries = [];

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;  // skip empty lines
        const parts = trimmed.split(':', 2);
        if (parts.length === 2) {
        const key = parts[0].trim();
        const value = parts[1].trim();
        if (key) {
            headerEntries.push({ key, value });
        }
        }
    }

    renderHeaders();
}

/**
 * Renders the current list of headers in 'headerEntries'
 * into the #headersPreview area. Each row has 2 text inputs and a remove button.
 */
function renderHeaders() {
    const previewDiv = document.getElementById('suggestion-list');
    previewDiv.innerHTML = ''; // clear old entries

    headerEntries.forEach((entry, idx) => {
        const row = document.createElement('div');
        row.className = 'header-row';
        row.innerHTML = `
        <input 
            type="text" 
            class="header-key" 
            value="${entry.key}" 
            oninput="updateKey(${idx}, this.value)"
        >
        <input 
            type="text" 
            class="header-value" 
            value="${entry.value}" 
            oninput="updateValue(${idx}, this.value)"
        >
        <button type="button" onclick="removeHeader(${idx})">X</button>
        `;
        previewDiv.appendChild(row);
    });
}

function removeHeader(index) {
    headerEntries.splice(index, 1);
    renderHeaders();
}

function updateKey(index, newKey) {
    headerEntries[index].key = newKey;
}

function updateValue(index, newValue) {
    headerEntries[index].value = newValue;
}

// function updateRawHeaders() {
//     // Example: gather header fields from right card
//     const headerInputs = document.querySelectorAll('.header-input'); 
//     let headersText = '';
//     headerInputs.forEach(input => {
//       // assuming each input has a data-key attribute for the header name
//       const key = input.dataset.key;
//       const value = input.value;
//       headersText += `${key}: ${value}\n`;
//     });
//     document.getElementById('raw_headers').value = headersText.trim();
//   }
  
//   // Attach updateRawHeaders to appropriate events:
//   document.querySelectorAll('.header-input').forEach(input => {
//     input.addEventListener('input', updateRawHeaders);
//   });  

// On form submission, combine the headerEntries array back into multiline text
document.getElementById('create-endpoint-form').addEventListener('submit', (e) => {
    // Reconstruct the multiline raw_headers so the server receives the final state
    const lines = headerEntries.map(h => `${h.key}: ${h.value}`);
    document.getElementById('raw_headers').value = lines.join('\n');
    // Then the form continues normal submission
});