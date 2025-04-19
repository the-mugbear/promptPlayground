// static/js/reports/report.js

// Store chart instances to manage their lifecycle
let chartInstances = {
  overall: null,
  transformations: null,
  runs: {} // Store per-run charts by run ID
};

/**
* Destroys all active chart instances.
*/
function destroyAllCharts() {
  if (chartInstances.overall) {
      chartInstances.overall.destroy();
      chartInstances.overall = null;
  }
  if (chartInstances.transformations) {
      chartInstances.transformations.destroy();
      chartInstances.transformations = null;
  }
  Object.values(chartInstances.runs).forEach(chart => chart.destroy());
  chartInstances.runs = {};
  // Hide placeholder containers again
  const overallContainer = document.getElementById('overall-chart-container');
  if (overallContainer) overallContainer.style.display = 'none';
  
  const transformationsContainer = document.getElementById('transformations-chart-container');
  if (transformationsContainer) transformationsContainer.style.display = 'none';
}

/**
* Initializes the report page functionality.
*/
function initializeReportPage() {
  const endpointSelect = document.getElementById('endpoint-select');
  const reportDetailsDiv = document.getElementById('report-details');
  
  if (!endpointSelect || !reportDetailsDiv) {
      console.error("Required elements (select or details div) not found!");
      return;
  }

  const baseUrl = endpointSelect.dataset.baseUrl;
  if (!baseUrl) {
      console.error("Base URL data attribute not found on endpoint select!");
      return;
  }

  endpointSelect.addEventListener('change', function() {
      const endpointId = this.value;

      // Clear previous results and destroy existing charts
      reportDetailsDiv.innerHTML = '';
      destroyAllCharts(); // Use the helper function

      if (!endpointId) {
          reportDetailsDiv.innerHTML = '<p>Please select an endpoint to view its report.</p>';
          return; 
      }

      const url = baseUrl.replace('0', endpointId);

      fetch(url)
          .then(response => {
              if (!response.ok) {
                  throw new Error(`HTTP error! status: ${response.status}`);
              }
              return response.json();
          })
          .then(data => {
              let endpointInfoHtml = `<h2>Report for Endpoint: <a href="/endpoints/${data.endpoint.id}">${data.endpoint.name}</a></h2>`;
              endpointInfoHtml += `<p><strong>Hostname:</strong> ${data.endpoint.hostname}</p>`;
              endpointInfoHtml += `<p><strong>Endpoint:</strong> ${data.endpoint.endpoint}</p>`;

              // --- Structure for a more organized layout ---
              let reportContentHtml = `<div class="report-container">`;

              // --- Charts Row ---
              reportContentHtml += `<div class="charts-row">`;
              // Overall Status Chart
              reportContentHtml += `<div id="overall-chart-dynamic-container" class="chart-container">
                                    <h3>Overall Status Distribution</h3>
                                    <div style="position: relative; height:300px; width:100%">
                                      <canvas id="overallMetricsChartDynamic"></canvas>
                                    </div>
                                  </div>`;
              // Failed Transformations Chart
              reportContentHtml += `<div id="transformations-chart-dynamic-container" class="chart-container">
                                    <h3>Failed Transformations by Type</h3>
                                    <div style="position: relative; height:300px; width:100%">
                                      <canvas id="transformationsChartDynamic"></canvas>
                                    </div>
                                  </div>`;
              reportContentHtml += `</div>`; // End Charts Row

              // --- Test Runs Section (Full Width) ---
              reportContentHtml += `<div class="test-runs-section">`;
              reportContentHtml += `<h3>Test Runs</h3>`;
              if (data.test_runs && data.test_runs.length > 0) {
                  reportContentHtml += `<div class="test-runs-grid">`;
                  data.test_runs.forEach(function(run) {
                      const createdAtFormatted = new Date(run.created_at).toLocaleString();
                      reportContentHtml += `<div class="test-run-item">`;
                      reportContentHtml +=   `<h4><a href="/test_runs/${run.id}">${run.name}</a></h4>`;
                      reportContentHtml +=   `<p>Status: <span class="status-${run.status.toLowerCase()}">${run.status}</span> | Created: ${createdAtFormatted}</p>`;
                      reportContentHtml +=   `<div class="run-content">`;
                      reportContentHtml +=     `<div class="per-run-metrics">`;
                      reportContentHtml +=       `<strong>Metrics:</strong> `;
                      reportContentHtml +=       `Total: ${run.metrics.total}, `;
                      reportContentHtml +=       `Passed: <span class="status-passed">${run.metrics.passed}</span>, `;
                      reportContentHtml +=       `Failed: <span class="status-failed">${run.metrics.failed}</span>, `;
                      reportContentHtml +=       `Skipped: <span class="status-skipped">${run.metrics.skipped}</span>, `;
                      reportContentHtml +=       `Pending: <span class="status-pending_review">${run.metrics.pending_review}</span>`;
                      reportContentHtml +=     `</div>`;
                      // Add chart next to metrics
                      reportContentHtml +=     `<div class="per-run-chart-container"><canvas id="run-chart-${run.id}"></canvas></div>`;
                      reportContentHtml +=   `</div>`; // End run-content
                      reportContentHtml += `</div>`; // End test-run-item
                  });
                  reportContentHtml += `</div>`; // End test-runs-grid
              } else {
                  reportContentHtml += `<p>No test runs found for this endpoint.</p>`;
              }
              reportContentHtml += `</div>`; // End Test Runs Section

              // --- Dialogues Section (Full Width) ---
              reportContentHtml += `<div class="dialogues report-section">`;
              reportContentHtml += `<h3>Dialogues</h3>`;
              if (data.dialogues && data.dialogues.length > 0) {
                  reportContentHtml += `<ul class="dialogues-list">`;
                  data.dialogues.forEach(function(dialogue) {
                    const createdAtFormatted = new Date(dialogue.created_at).toLocaleString();
                    reportContentHtml += `<li><a href="/dialogues/${dialogue.id}">${dialogue.source} - ${createdAtFormatted}</a></li>`;
                  });
                  reportContentHtml += `</ul>`;
              } else {
                reportContentHtml += `<p>No dialogues found for this endpoint.</p>`;
              }
              reportContentHtml += `</div>`; // End Dialogues Section

              reportContentHtml += `</div>`; // End report-container

              // --- Dialogues Section (Below Grid) ---
              // reportContentHtml += `<div class="dialogues report-section">`;
              // reportContentHtml += `<h3>Dialogues</h3>`;
              // // ... (existing dialogues list generation logic) ...
              //  if (data.dialogues && data.dialogues.length > 0) {
              //   reportContentHtml += `<ul>`;
              //   data.dialogues.forEach(function(dialogue) {
              //      const createdAtFormatted = new Date(dialogue.created_at).toLocaleString();
              //      reportContentHtml += `<li><a href="/dialogues/${dialogue.id}">${dialogue.source} - ${createdAtFormatted}</a></li>`;
              //   });
              //   reportContentHtml += `</ul>`;
              // } else {
              //   reportContentHtml += `<p>No dialogues found for this endpoint.</p>`;
              // }
              // reportContentHtml += `</div>`;


              // Update the DOM with endpoint info first, then the rest
              reportDetailsDiv.innerHTML = endpointInfoHtml + reportContentHtml;
              
              // --- Render Charts AFTER HTML is in the DOM ---
              // Ensure the dynamic canvas elements exist before rendering
              const overallCanvasDynamic = document.getElementById('overallMetricsChartDynamic');
              const transformationsCanvasDynamic = document.getElementById('transformationsChartDynamic');

              if (overallCanvasDynamic) {
                   renderOverallMetricsChart(data.overall_metrics, overallCanvasDynamic);
                   // Show the container if needed (might not be necessary if created dynamically)
                   // document.getElementById('overall-chart-dynamic-container').style.display = 'block';
              }
               if (transformationsCanvasDynamic && Object.keys(data.overall_metrics.failed_transformations).length > 0) {
                   renderFailedTransformationsChart(data.overall_metrics.failed_transformations, transformationsCanvasDynamic);
                   // document.getElementById('transformations-chart-dynamic-container').style.display = 'block';
              } else if (transformationsCanvasDynamic) {
                   // Optionally display a message if no transformation data
                   transformationsCanvasDynamic.parentElement.innerHTML += '<p>No failed transformation data to display.</p>';
               }


              // Render per-run charts
              data.test_runs.forEach(run => {
                  renderPerRunChart(run.metrics, `run-chart-${run.id}`);
              });

          })
          .catch(error => {
              console.error('Error loading report details:', error);
              reportDetailsDiv.innerHTML = `<p class="error-message">Error loading report details. Please check the console or try again later.</p>`;
          });
  });
}

/**
* Renders the overall metrics chart (e.g., Pie)
*/
function renderOverallMetricsChart(metrics, canvasElement) {
  if (!canvasElement || typeof Chart === 'undefined') return;
  const ctx = canvasElement.getContext('2d');
  const chartData = { /* ... Same data as before ... */ 
      labels: ['Passed', 'Failed', 'Skipped', 'Pending Review'],
      datasets: [{
          label: 'Overall Test Run Statuses',
          data: [ metrics.passed, metrics.failed, metrics.skipped, metrics.pending_review ],
          backgroundColor: [ /* ... colors ... */ 
              'rgba(75, 192, 192, 0.7)', 'rgba(255, 99, 132, 0.7)',
              'rgba(255, 206, 86, 0.7)', 'rgba(153, 102, 255, 0.7)' ],
          borderColor: [ /* ... border colors ... */ 
              'rgba(75, 192, 192, 1)', 'rgba(255, 99, 132, 1)',
              'rgba(255, 206, 86, 1)', 'rgba(153, 102, 255, 1)' ],
          borderWidth: 1
      }]};

  if (chartInstances.overall) chartInstances.overall.destroy(); // Destroy previous if exists
  chartInstances.overall = new Chart(ctx, {
      type: 'pie', 
      data: chartData,
      options: { /* ... options like responsiveness, legend ... */
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: 'top' } }
      }
  });
}

/**
* Renders the failed transformations chart (e.g., Bar)
*/
function renderFailedTransformationsChart(transformationsData, canvasElement) {
  if (!canvasElement || typeof Chart === 'undefined' || Object.keys(transformationsData).length === 0) {
       // Don't render if no data or canvas/Chartjs missing
      return;
  }
  const ctx = canvasElement.getContext('2d');
  const labels = Object.keys(transformationsData);
  const dataValues = Object.values(transformationsData);

  const chartData = {
      labels: labels,
      datasets: [{
          label: 'Count',
          data: dataValues,
          backgroundColor: 'rgba(255, 159, 64, 0.7)', // Example color Orange
          borderColor: 'rgba(255, 159, 64, 1)',
          borderWidth: 1
      }]
  };
  
  if (chartInstances.transformations) chartInstances.transformations.destroy();
  chartInstances.transformations = new Chart(ctx, {
      type: 'bar',
      data: chartData,
      options: {
          indexAxis: 'y', // Makes labels horizontal, bars vertical - easier for long names
          responsive: true,
          maintainAspectRatio: false,
           plugins: { legend: { display: false } } // Legend might be redundant for single dataset
      }
  });
}

/**
* Renders a small chart for a single test run's metrics.
* @param {object} metrics - The metrics object for the specific run.
* @param {string} canvasId - The ID of the canvas element for this run.
*/
function renderPerRunChart(metrics, canvasId) {
  const canvasElement = document.getElementById(canvasId);
  if (!canvasElement || typeof Chart === 'undefined' || metrics.total === 0) {
       // Don't render if no executions or canvas/Chartjs missing
       if(canvasElement) canvasElement.parentElement.innerHTML = '<i>No executions for this run.</i>'; // Add message if canvas exists but no data
      return;
  } 
  const ctx = canvasElement.getContext('2d');
  const chartData = {
      labels: ['Passed', 'Failed', 'Skipped', 'Pending'],
      datasets: [{
          data: [ metrics.passed, metrics.failed, metrics.skipped, metrics.pending_review ],
          backgroundColor: [ /* ... colors (same as overall) ... */
              'rgba(75, 192, 192, 0.7)', 'rgba(255, 99, 132, 0.7)',
              'rgba(255, 206, 86, 0.7)', 'rgba(153, 102, 255, 0.7)' ],
           borderWidth: 1 // Less prominent border maybe
      }]
  };

  // Destroy previous chart for this specific run ID if it exists
  if (chartInstances.runs[canvasId]) {
      chartInstances.runs[canvasId].destroy();
  }

  chartInstances.runs[canvasId] = new Chart(ctx, {
      type: 'doughnut', // Doughnut or pie looks good small
      data: chartData,
      options: {
          responsive: true,
          maintainAspectRatio: true, // Keep aspect ratio for small charts
          plugins: {
              legend: { display: false }, // Hide legend for small charts
              tooltip: { enabled: true }, // Keep tooltips
               title: { // Optional small title
                   display: false, 
                   // text: 'Run Status'
               }
          }
      }
  });
}

// Initialize page
document.addEventListener('DOMContentLoaded', initializeReportPage);