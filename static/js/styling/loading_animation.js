// JavaScript to control the loader visibility
const apiLoader = document.getElementById('apiLoader');
apiLoader.style.display = 'none'; // Hide by default

// Show loader before sending request
function showLoader() {
  apiLoader.style.display = 'block';
}

// Hide loader after receiving response
function hideLoader() {
  apiLoader.style.display = 'none';
}

// Example of using with fetch API
async function sendApiRequest(url, data) {
  showLoader();
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
    
    const result = await response.json();
    return result;
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  } finally {
    hideLoader();
  }
}

// For multiple loaders, create a more versatile function:
function createLoader(containerId, message = "Processing...") {
  const container = document.getElementById(containerId);
  const loader = document.createElement('div');
  loader.className = 'typing-loader';
  loader.textContent = message;
  loader.style.display = 'none';
  container.appendChild(loader);
  
  return {
    show: () => loader.style.display = 'block',
    hide: () => loader.style.display = 'none'
  };
}

// Usage:
// const resultsLoader = createLoader('results-container', 'Fetching data...');
// resultsLoader.show();
// // Do API call
// resultsLoader.hide();