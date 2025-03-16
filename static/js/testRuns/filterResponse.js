
document.addEventListener('DOMContentLoaded', function(){
    // Select all JSON response elements.
    const responseElements = document.querySelectorAll('.json-response');
    let allKeys = new Set();
    
    // Gather keys from each JSON response.
    responseElements.forEach((elem) => {
        try {
            const text = elem.textContent.trim();
            if(text) {
                const data = JSON.parse(text);
                if (typeof data === 'object' && data !== null) {
                    Object.keys(data).forEach(key => allKeys.add(key));
                }
            }
        } catch (e) {
            // If not valid JSON, ignore.
        }
    });
    
    // Create the dropdown if keys were found.
    if(allKeys.size > 0) {
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
            if(!elem.hasAttribute('data-original')) {
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
                    if(selectedKey === ""){
                        // Show full JSON.
                        elem.textContent = JSON.stringify(data, null, 2);
                    } else {
                        // Show only the value for the selected key.
                        const value = data[selectedKey];
                        elem.textContent = JSON.stringify(value, null, 2);
                    }
                } catch (e) {
                    // If parsing fails, leave the content unchanged.
                }
            });
        });
    }
});

