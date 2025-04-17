/**
 * Script Name: FormFieldSyncer
 * Purpose: Copy values from visible form inputs into hidden inputs
 *          so that on POST the test-endpoint form carries the current values.
 * Usage: Include this script on pages that render both visible fields
 *        (e.g. hostname, endpoint, payload, headers) and a hidden
 *        test-endpoint-form with matching input[name="…"] fields.
 */

document.addEventListener('DOMContentLoaded', function () {
  // Visible fields rendered in the main form (via Jinja):
  const hostnameField = document.getElementById('hostname');
  const endpointField = document.getElementById('endpoint');
  const payloadField  = document.getElementById('http_payload');
  const headersField  = document.getElementById('raw_headers');

  // Corresponding hidden inputs inside the test-endpoint form:
  const testHostname = document.querySelector(
    'form#test-endpoint-form input[name="hostname"]'
  );
  const testEndpoint = document.querySelector(
    'form#test-endpoint-form input[name="endpoint"]'
  );
  const testPayload = document.querySelector(
    'form#test-endpoint-form input[name="http_payload"]'
  );
  const testHeaders = document.querySelector(
    'form#test-endpoint-form input[name="raw_headers"]'
  );

  /**
   * Copies values from the visible inputs into the hidden test-endpoint inputs.
   * This ensures that when the form is submitted, it carries the latest values.
   */
  function syncFields() {
    testHostname.value = hostnameField.value;
    testEndpoint.value = endpointField.value;
    testPayload.value  = payloadField.value;
    testHeaders.value  = headersField.value;
  }

  // 1) Keep hidden inputs up-to-date as the user types in the visible fields
  hostnameField.addEventListener('input', syncFields);
  endpointField.addEventListener('input', syncFields);
  payloadField.addEventListener('input', syncFields);
  headersField.addEventListener('input', syncFields);

  // 2) Initialize hidden inputs on page load, before any typing occurs
  syncFields();
});
