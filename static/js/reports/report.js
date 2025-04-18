// static/js/report.js

/**
 * Initializes the report page functionality.
 * Attaches an event listener to the endpoint selection dropdown.
 */
function initializeReportPage() {
    const endpointSelect = document.getElementById('endpoint-select');
    const reportDetailsDiv = document.getElementById('report-details');
    // const metricsChartCanvas = document.getElementById('metricsChart'); // Keep reference for charting
  
    if (!endpointSelect) {
      console.error("Endpoint select dropdown not found!");
      return;
    }
  
    // Read the base URL from the data attribute
    const baseUrl = endpointSelect.dataset.baseUrl;
    if (!baseUrl) {
        console.error("Base URL data attribute not found on endpoint select!");
        return;
    }
  
    endpointSelect.addEventListener('change', function() {
      const endpointId = this.value;
  
      // Clear previous results and chart
      reportDetailsDiv.innerHTML = '';
      // TODO: Clear or update chart here if it exists
      // Example: if (window.myChart) { window.myChart.destroy(); }
  
      if (!endpointId) {
        return; // Do nothing if the default option is selected
      }
  
      // Construct the specific URL for the selected endpoint
      const url = baseUrl.replace('0', endpointId);
  
      fetch(url)
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          // Build the HTML structure more cleanly
          let html = `<h2>Report for Endpoint: <a href="/endpoints/${data.endpoint.id}">${data.endpoint.name}</a></h2>`;
          html += `<p><strong>Hostname:</strong> ${data.endpoint.hostname}</p>`;
          html += `<p><strong>Endpoint:</strong> ${data.endpoint.endpoint}</p>`;
  
          // --- Metrics Section ---
          html += `<div class="metrics report-section">`;
          html += `<h3>Metrics</h3>`;
          html += `<ul>`;
          html += `<li>Total Executions: ${data.metrics.total_executions}</li>`;
          html += `<li>Passed: ${data.metrics.passed}</li>`;
          html += `<li>Failed: ${data.metrics.failed}</li>`;
          html += `<li>Skipped: ${data.metrics.skipped}</li>`;
          html += `<li>Pending Review: ${data.metrics.pending_review}</li>`;
          html += `</ul>`;
          html += `</div>`;
  
          // --- Failed Transformations Section ---
          html += `<div class="failed-transformations report-section">`;
          html += `<h3>Failed Transformations</h3>`;
          if (Object.keys(data.metrics.failed_transformations).length > 0) {
            html += `<ul>`;
            for (const key in data.metrics.failed_transformations) {
              // Use hasOwnProperty for safer iteration (good practice)
              if (Object.hasOwnProperty.call(data.metrics.failed_transformations, key)) {
                  html += `<li>${key}: ${data.metrics.failed_transformations[key]}</li>`;
              }
            }
            html += `</ul>`;
          } else {
            html += `<p>No failed transformation data.</p>`;
          }
          html += `</div>`;
  
          // --- Test Runs Section ---
          html += `<div class="test-runs report-section">`;
          html += `<h3>Test Runs</h3>`;
          if (data.test_runs.length > 0) {
            // Add a class to the table for specific styling
            html += `<table class="test-runs-table">`;
            html += `<thead><tr><th>Name</th><th>Status</th><th>Created At</th></tr></thead>`;
            html += `<tbody>`;
            data.test_runs.forEach(function(run) {
              // Consider formatting the date/time here if needed
              const createdAtFormatted = new Date(run.created_at).toLocaleString(); // Example formatting
              html += `<tr>`;
              html += `<td><a href="/test_runs/${run.id}">${run.name}</a></td>`;
              // Add a class based on status for potential styling
              html += `<td class="status-${run.status.toLowerCase()}">${run.status}</td>`;
              html += `<td>${createdAtFormatted}</td>`;
              html += `</tr>`;
            });
            html += `</tbody></table>`;
          } else {
            html += `<p>No test runs found for this endpoint.</p>`;
          }
          html += `</div>`;
  
          // --- Dialogues Section ---
          html += `<div class="dialogues report-section">`;
          html += `<h3>Dialogues for this Endpoint</h3>`;
          if (data.dialogues.length > 0) {
            html += `<ul>`;
            data.dialogues.forEach(function(dialogue) {
               const createdAtFormatted = new Date(dialogue.created_at).toLocaleString(); // Example formatting
              html += `<li><a href="/dialogues/${dialogue.id}">${dialogue.source} - ${createdAtFormatted}</a></li>`;
            });
            html += `</ul>`;
          } else {
            html += `<p>No dialogues found for this endpoint.</p>`;
          }
          html += `</div>`;
  
          reportDetailsDiv.innerHTML = html;
  
          // TODO: Call charting function here, passing data.metrics
          // Example: renderMetricsChart(data.metrics, metricsChartCanvas);
  
        })
        .catch(error => {
          console.error('Error loading report details:', error);
          reportDetailsDiv.innerHTML = `<p class="error-message">Error loading report details. Please check the console or try again later.</p>`;
        });
    });
  }
    
  // Ensure the DOM is fully loaded before running the initialization function
  document.addEventListener('DOMContentLoaded', initializeReportPage);