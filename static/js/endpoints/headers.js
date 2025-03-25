// We'll keep an array in JS to track the parsed headers
let headerEntries = [];

// Robust cookie parsing function
function parseCookieHeader(cookieString) {
    const cookiePairs = [];
    let currentPair = '';
    let insideQuotes = false;
    
    for (let i = 0; i < cookieString.length; i++) {
        const char = cookieString[i];
        
        if (char === '"' && cookieString[i-1] !== '\\') {
            insideQuotes = !insideQuotes;
        }
        
        if (char === ';' && !insideQuotes) {
            // End of a cookie pair
            if (currentPair.trim()) {
                const [name, ...valueParts] = currentPair.trim().split('=');
                cookiePairs.push({
                    name: name.trim(),
                    value: valueParts.join('=').trim().replace(/^"|"$/g, '')
                });
            }
            currentPair = '';
        } else {
            currentPair += char;
        }
    }
    
    // Add the last cookie
    if (currentPair.trim()) {
        const [name, ...valueParts] = currentPair.trim().split('=');
        cookiePairs.push({
            name: name.trim(),
            value: valueParts.join('=').trim().replace(/^"|"$/g, '')
        });
    }
    
    return cookiePairs;
}

// Automatically parse headers when the raw_headers textarea is modified
// use indexOf() to find the first colon and then use substring() so that any additional colons in the value remain intact
function parseHeaders() {
    const rawText = document.getElementById('raw_headers').value;
    const lines = rawText.split('\n');
    headerEntries = [];

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;  // skip empty lines

        // Use indexOf to find the first colon, preserving additional colons in the value.
        const colonIndex = trimmed.indexOf(':');
        if (colonIndex === -1) continue;  // ignore lines with no colon

        const key = trimmed.substring(0, colonIndex).trim();
        const value = trimmed.substring(colonIndex + 1).trim();
        let entry = { key, value };

        // Special handling for Cookie header
        if (key.toLowerCase() === 'cookie') {
            entry.cookiePairs = parseCookieHeader(value);
        }
        headerEntries.push(entry);
    }
    renderHeaders();
}


function renderHeaders() {
    const previewDiv = document.getElementById('suggestion-list');
    previewDiv.innerHTML = ''; // clear old entries

    headerEntries.forEach((entry, idx) => {
        const row = document.createElement('div');
        row.className = 'header-row';
        
        // Check if this is a Cookie header with cookiePairs available
        if (entry.key.toLowerCase() === 'cookie' && entry.cookiePairs) {
            // Build HTML for each cookie pair
            let cookieHtml = entry.cookiePairs.map((cookie, cIdx) => {
                return `<div class="cookie-row">
                            <input type="text" class="cookie-key" value="${cookie.name}" oninput="updateCookieKey(${idx}, ${cIdx}, this.value)">
                            <input type="text" class="cookie-value" value="${cookie.value}" oninput="updateCookieValue(${idx}, ${cIdx}, this.value)">
                            <button type="button" onclick="removeCookie(${idx}, ${cIdx})">X</button>
                        </div>`;
            }).join('');
            
            row.innerHTML = `
                <input type="text" class="header-key" value="${entry.key}" oninput="updateKey(${idx}, this.value)">
                <div class="cookie-container">${cookieHtml}</div>
                <button type="button" onclick="removeHeader(${idx})">X</button>
                <button type="button" onclick="addCookie(${idx})">Add Cookie</button>
            `;
        } else {
            row.innerHTML = `
                <input type="text" class="header-key" value="${entry.key}" oninput="updateKey(${idx}, this.value)">
                <input type="text" class="header-value" value="${entry.value}" oninput="updateValue(${idx}, this.value)">
                <button type="button" onclick="removeHeader(${idx})">X</button>
            `;
        }
        previewDiv.appendChild(row);
    });
    
    // Update the raw textarea so that it stays in sync with headerEntries.
    updateRawHeaders();
}

// The rest of the functions remain the same as in your original script
function updateRawHeaders() {
    const rawHeadersText = headerEntries.map(h => {
        if (h.key.toLowerCase() === 'cookie' && h.cookiePairs) {
            // Reconstruct the Cookie header from individual cookie pairs.
            const cookieString = h.cookiePairs.map(c => `${c.name}=${c.value}`).join('; ');
            return `${h.key}: ${cookieString}`;
        } else {
            return `${h.key}: ${h.value}`;
        }
    }).join('\n');
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

// Cookie-specific functions
function updateCookieKey(headerIdx, cookieIdx, newName) {
    headerEntries[headerIdx].cookiePairs[cookieIdx].name = newName;
    updateRawHeaders();
}

function updateCookieValue(headerIdx, cookieIdx, newValue) {
    headerEntries[headerIdx].cookiePairs[cookieIdx].value = newValue;
    updateRawHeaders();
}

function removeCookie(headerIdx, cookieIdx) {
    headerEntries[headerIdx].cookiePairs.splice(cookieIdx, 1);
    updateRawHeaders();
    renderHeaders();
}

function addCookie(headerIdx) {
    headerEntries[headerIdx].cookiePairs.push({name: '', value: ''});
    updateRawHeaders();
    renderHeaders();
}

// On form submission, combine the headerEntries array back into multiline text so the server receives the final state.
document.getElementById('create-endpoint-form').addEventListener('submit', (e) => {
    const lines = headerEntries.map(h => {
        if (h.key.toLowerCase() === 'cookie' && h.cookiePairs) {
            const cookieString = h.cookiePairs.map(c => `${c.name}=${c.value}`).join('; ');
            return `${h.key}: ${cookieString}`;
        } else {
            return `${h.key}: ${h.value}`;
        }
    });
    document.getElementById('raw_headers').value = lines.join('\n');
});