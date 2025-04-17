// Script: HeaderEditor
// Purpose: Parse a raw “Headers:” textarea into editable rows (including special Cookie parsing),
//          keep both representations (textarea and UI rows) in sync, and serialize back on submit.

// We'll keep an array in JS to track the parsed headers
let headerEntries = [];

/**
 * parseCookieHeader
 * -----------------
 * Takes a single Cookie header string and returns an array of {name, value} pairs.
 * Handles semicolons inside quoted values by tracking when we're inside quotes.
 */
function parseCookieHeader(cookieString) {
  const cookiePairs = [];
  let currentPair = '';
  let insideQuotes = false;
  
  for (let i = 0; i < cookieString.length; i++) {
    const char = cookieString[i];
    // Flip insideQuotes when we see an unescaped double quote
    if (char === '"' && cookieString[i - 1] !== '\\') {
      insideQuotes = !insideQuotes;
    }
    // A semicolon outside quotes marks the end of one cookie
    if (char === ';' && !insideQuotes) {
      if (currentPair.trim()) {
        const [name, ...valueParts] = currentPair.trim().split('=');
        cookiePairs.push({
          name:  name.trim(),
          value: valueParts.join('=').trim().replace(/^"|"$/g, '')
        });
      }
      currentPair = '';
    } else {
      currentPair += char;
    }
  }
  // Add final cookie pair if any remains
  if (currentPair.trim()) {
    const [name, ...valueParts] = currentPair.trim().split('=');
    cookiePairs.push({
      name:  name.trim(),
      value: valueParts.join('=').trim().replace(/^"|"$/g, '')
    });
  }
  return cookiePairs;
}

/**
 * parseHeaders
 * ------------
 * Reads the raw_headers textarea, splits on lines, and builds headerEntries[].
 * For each line:
 *  - Ignores blank lines or lines without a colon.
 *  - Splits at the first colon to get key and value.
 *  - If the header is “Cookie”, calls parseCookieHeader for its sub-pairs.
 * Finally, calls renderHeaders() to update the UI.
 */
function parseHeaders() {
  const rawText = document.getElementById('raw_headers').value;
  const lines = rawText.split('\n');
  headerEntries = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;              // skip empty
    const colonIndex = trimmed.indexOf(':');
    if (colonIndex === -1) continue;     // skip malformed

    const key   = trimmed.substring(0, colonIndex).trim();
    const value = trimmed.substring(colonIndex + 1).trim();
    const entry = { key, value };

    // If it's a Cookie header, parse sub-pairs
    if (key.toLowerCase() === 'cookie') {
      entry.cookiePairs = parseCookieHeader(value);
    }
    headerEntries.push(entry);
  }

  renderHeaders();
}

/**
 * renderHeaders
 * -------------
 * Finds the first available container (editable or read-only) to display header rows.
 * Clears existing content, then for each entry:
 *  - If Cookie header, builds inputs for each cookie name/value and add/remove buttons.
 *  - Otherwise, builds inputs for key and value and a remove button.
 * Appends each row, then calls updateRawHeaders() to sync back to textarea if needed.
 */
function renderHeaders() {
  const previewDiv = document.getElementById('suggestion-list')
                  || document.getElementById('editableHeaderPreview')
                  || document.getElementById('readOnlyHeadersDisplay');
  if (!previewDiv) {
    console.error("No container found for header preview.");
    return;
  }
  previewDiv.innerHTML = '';

  headerEntries.forEach((entry, idx) => {
    const row = document.createElement('div');
    row.className = 'header-row';

    if (entry.key.toLowerCase() === 'cookie' && entry.cookiePairs) {
      // Build HTML for each cookie pair
      const cookieHtml = entry.cookiePairs.map((cookie, cIdx) => `
        <div class="cookie-row">
          <input type="text" class="cookie-key"   value="${cookie.name}"
                 oninput="updateCookieKey(${idx}, ${cIdx}, this.value)">
          <input type="text" class="cookie-value" value="${cookie.value}"
                 oninput="updateCookieValue(${idx}, ${cIdx}, this.value)">
          <button type="button" onclick="removeCookie(${idx}, ${cIdx})">X</button>
        </div>
      `).join('');
      row.innerHTML = `
        <input type="text" class="header-key" value="${entry.key}"
               oninput="updateKey(${idx}, this.value)">
        <div class="cookie-container">${cookieHtml}</div>
        <button type="button" onclick="removeHeader(${idx})">Remove Header</button>
        <button type="button" onclick="addCookie(${idx})">Add Cookie</button>
      `;
    } else {
      // Regular header row
      row.innerHTML = `
        <input type="text" class="header-key"   value="${entry.key}"
               oninput="updateKey(${idx}, this.value)">
        <input type="text" class="header-value" value="${entry.value}"
               oninput="updateValue(${idx}, this.value)">
        <button type="button" onclick="removeHeader(${idx})">Remove</button>
      `;
    }
    previewDiv.appendChild(row);
  });

  updateRawHeaders();
}

/**
 * updateRawHeaders
 * ----------------
 * Serializes headerEntries[] back into the raw_headers textarea.
 * Only runs if the textarea is NOT focused, to avoid overwriting in-progress edits.
 */
function updateRawHeaders() {
  const rawElem = document.getElementById('raw_headers');
  if (document.activeElement === rawElem) return;

  const lines = headerEntries.map(h => {
    if (h.key.toLowerCase() === 'cookie' && h.cookiePairs) {
      // Serialize cookie pairs with semicolons
      const cookieString = h.cookiePairs.map(c => `${c.name}=${c.value}`).join('; ');
      return `${h.key}: ${cookieString}`;
    } else {
      return `${h.key}: ${h.value}`;
    }
  });
  rawElem.value = lines.join('\n');
}

// Keep textarea and parsedHeaders in sync:
// On blur, update the textarea from headerEntries.
document.getElementById('raw_headers').addEventListener('blur', updateRawHeaders);
// On input, reparses headers into headerEntries and rerenders rows.
document.getElementById('raw_headers').addEventListener('input', parseHeaders);

/**
 * Core row operations: remove or update header entries.
 * These always call updateRawHeaders (and sometimes renderHeaders) to keep both views in sync.
 */
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

/** Cookie-specific helpers **/
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
  renderHeaders();
}
function addCookie(headerIdx) {
  headerEntries[headerIdx].cookiePairs.push({ name: '', value: '' });
  renderHeaders();
}

/**
 * Final sync on form submission:
 * Before sending, serialize headerEntries[] one last time into the textarea
 * so the server receives the up-to-date headers.
 */
document.getElementById('create-endpoint-form').addEventListener('submit', () => {
  const lines = headerEntries.map(h => {
    if (h.key.toLowerCase() === 'cookie' && h.cookiePairs) {
      const cookieString = h.cookiePairs.map(c => `${c.name}=${c.value}`).join('; ');
      return `${h.key}: ${cookieString}`;
    }
    return `${h.key}: ${h.value}`;
  });
  document.getElementById('raw_headers').value = lines.join('\n');
});
