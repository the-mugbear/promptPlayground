// Jinja templates are rendered on the server before being sent to the browser.
// On the initial (GET) request to display the page, request.form has no data because there was no POST yet.
// Therefore we use the script below to copy the values from the visible form fields into the hidden form fields

  document.addEventListener('DOMContentLoaded', function () {
    const hostnameField = document.getElementById('hostname');
    const endpointField = document.getElementById('endpoint');
    const payloadField = document.getElementById('http_payload');
    const headersField = document.getElementById('raw_headers');

    const testHostname = document.querySelector('form#test-endpoint-form input[name="hostname"]');
    const testEndpoint = document.querySelector('form#test-endpoint-form input[name="endpoint"]');
    const testPayload = document.querySelector('form#test-endpoint-form input[name="http_payload"]');
    const testHeaders = document.querySelector('form#test-endpoint-form input[name="raw_headers"]');

    function syncFields() {
      testHostname.value = hostnameField.value;
      testEndpoint.value = endpointField.value;
      testPayload.value = payloadField.value;
      testHeaders.value = headersField.value;
    }

    // 1) Attach event listeners to keep them in sync as user types
    hostnameField.addEventListener('input', syncFields);
    endpointField.addEventListener('input', syncFields);
    payloadField.addEventListener('input', syncFields);
    headersField.addEventListener('input', syncFields);

    // 2) **Initialize** hidden fields on page load
    syncFields();
  });

