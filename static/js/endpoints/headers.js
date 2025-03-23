// We'll keep an array in JS to track the parsed headers
let headerEntries = [];

// Automatically parse headers when the raw_headers textarea is modified
document.getElementById('raw_headers').addEventListener('input', parseHeaders);

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
    // Update the raw textarea so that it stays in sync with headerEntries.
    updateRawHeaders();
}

function updateRawHeaders() {
    const rawHeadersText = headerEntries.map(h => `${h.key}: ${h.value}`).join('\n');
    document.getElementById('raw_headers').value = rawHeadersText;
}

function removeHeader(index) {
    headerEntries.splice(index, 1);
    renderHeaders();
}

function updateKey(index, newKey) {
    headerEntries[index].key = newKey;
    updateRawHeaders();
}

function updateValue(index, newValue) {
    headerEntries[index].value = newValue;
    updateRawHeaders();
}

// On form submission, combine the headerEntries array back into multiline text so the server receives the final state.
document.getElementById('create-endpoint-form').addEventListener('submit', (e) => {
    const lines = headerEntries.map(h => `${h.key}: ${h.value}`);
    document.getElementById('raw_headers').value = lines.join('\n');
});
