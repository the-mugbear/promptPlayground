document.addEventListener('DOMContentLoaded', function(){
// Utility function to recursively extract keys from an object.
function extractKeys(obj) {
    let keys = new Set();
    if (typeof obj === 'object' && obj !== null) {
    for (let key in obj) {
        keys.add(key);
        // If the value is an object (or array), recursively extract its keys.
        if (typeof obj[key] === 'object' && obj[key] !== null) {
        extractKeys(obj[key]).forEach(childKey => keys.add(childKey));
        }
    }
    }
    return keys;
}

// Utility function to recursively find and return the value for a given key.
function findKey(obj, targetKey) {
    if (obj && typeof obj === 'object') {
    if (obj.hasOwnProperty(targetKey)) {
        return obj[targetKey];
    }
    for (let key in obj) {
        if (typeof obj[key] === 'object') {
        let found = findKey(obj[key], targetKey);
        if (found !== undefined) {
            return found;
        }
        }
    }
    }
    return undefined;
}

// Select all JSON response elements.
const responseElements = document.querySelectorAll('.json-response');
let allKeys = new Set();

// Gather keys from each JSON response using the recursive extractKeys function.
responseElements.forEach((elem) => {
    try {
    const text = elem.textContent.trim();
    if (text) {
        const data = JSON.parse(text);
        extractKeys(data).forEach(key => allKeys.add(key));
    }
    } catch (e) {
    // If not valid JSON, ignore.
    }
});

// Create the dropdown if keys were found.
if (allKeys.size > 0) {
    const keysArray = Array.from(allKeys).sort();
    const filterContainer = document.getElementById('filter-container');
    
    const label = document.createElement('label');
    label.setAttribute('for', 'json-key-filter');
    label.innerText = 'Filter response by key: ';
    
    const select = document.createElement('select');
    select.id = 'json-key-filter';
    
    // Option to show full JSON.
    const defaultOption = document.createElement('option');
    defaultOption.value = "";
    defaultOption.text = "Show full JSON";
    select.appendChild(defaultOption);
    
    keysArray.forEach(key => {
    const option = document.createElement('option');
    option.value = key;
    option.text = key;
    select.appendChild(option);
    });
    
    filterContainer.appendChild(label);
    filterContainer.appendChild(select);
    
    // Store original JSON content for each element.
    responseElements.forEach((elem) => {
    if (!elem.hasAttribute('data-original')) {
        elem.setAttribute('data-original', elem.textContent);
    }
    });
    
    // When a key is selected, update each response.
    select.addEventListener('change', function(){
    const selectedKey = select.value;
    responseElements.forEach((elem) => {
        try {
        const original = elem.getAttribute('data-original');
        const data = JSON.parse(original);
        if (selectedKey === "") {
            // Show full JSON.
            elem.textContent = JSON.stringify(data, null, 2);
        } else {
            // Recursively search for the key and display its value.
            const value = findKey(data, selectedKey);
            elem.textContent = JSON.stringify(value, null, 2);
        }
        } catch (e) {
        // If parsing fails, leave the content unchanged.
        }
    });
    });
}
});
