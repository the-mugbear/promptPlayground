document.getElementById('endpoint-select').addEventListener('change', function() {
    var endpointId = this.value;
    if (!endpointId) {
      document.getElementById('report-details').innerHTML = '';
      return;
    }
    // Construct the AJAX URL; note the empty string placeholder is appended with the endpointId.
    var baseUrl = '{{ url_for("report_bp.report_ajax", endpoint_id=0) }}';
    var url = baseUrl.replace('0', endpointId);
    fetch(url)
      .then(response => response.json())
      .then(data => {
        var html = '<h2>Report for Endpoint: ' + data.endpoint.name + '</h2>';
        html += '<p><strong>Hostname:</strong> ' + data.endpoint.hostname + '</p>';
        html += '<p><strong>Endpoint:</strong> ' + data.endpoint.endpoint + '</p>';
        html += '<h3>Metrics</h3>';
        html += '<ul>';
        html += '<li>Total Executions: ' + data.metrics.total_executions + '</li>';
        html += '<li>Passed: ' + data.metrics.passed + '</li>';
        html += '<li>Failed: ' + data.metrics.failed + '</li>';
        html += '<li>Skipped: ' + data.metrics.skipped + '</li>';
        html += '<li>Pending Review: ' + data.metrics.pending_review + '</li>';
        html += '</ul>';
        html += '<h3>Failed Transformations</h3>';
        if (Object.keys(data.metrics.failed_transformations).length > 0) {
          html += '<ul>';
          for (var key in data.metrics.failed_transformations) {
            html += '<li>' + key + ': ' + data.metrics.failed_transformations[key] + '</li>';
          }
          html += '</ul>';
        } else {
          html += '<p>No failed transformation data.</p>';
        }
        html += '<h3>Test Runs</h3>';
        if (data.test_runs.length > 0) {
          html += '<table border="1" cellpadding="5">';
          html += '<thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Created At</th></tr></thead>';
          html += '<tbody>';
          data.test_runs.forEach(function(run) {
            html += '<tr>';
            html += '<td>' + run.id + '</td>';
            html += '<td>' + run.name + '</td>';
            html += '<td>' + run.status + '</td>';
            html += '<td>' + run.created_at + '</td>';
            html += '</tr>';
          });
          html += '</tbody></table>';
        } else {
          html += '<p>No test runs found for this endpoint.</p>';
        }
        document.getElementById('report-details').innerHTML = html;
      })
      .catch(error => {
        document.getElementById('report-details').innerHTML = '<p>Error loading report details.</p>';
      });
  });