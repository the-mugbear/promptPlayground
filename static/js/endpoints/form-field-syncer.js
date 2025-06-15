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
  const baseUrlField = document.getElementById('base_url');
  const pathField = document.getElementById('path');
  const payloadTemplateField  = document.getElementById('payload_template');
  const headersField  = document.getElementById('raw_headers');

  // Corresponding hidden inputs inside the test-endpoint form:
  const testBaseUrl = document.querySelector(
    'form#test-endpoint-form input[name="base_url"]'
  );
  const testPath = document.querySelector(
    'form#test-endpoint-form input[name="path"]'
  );
  const testPayloadTemplate = document.querySelector(
    'form#test-endpoint-form input[name="payload_template"]'
  );
  const testHeaders = document.querySelector(
    'form#test-endpoint-form input[name="raw_headers"]'
  );

  /**
   * Copies values from the visible inputs into the hidden test-endpoint inputs.
   * This ensures that when the form is submitted, it carries the latest values.
   */
  function syncFields() {
    testBaseUrl.value = baseUrlField.value;
    testPath.value = pathField.value;
    testPayloadTemplate.value  = payloadTemplateField.value;
    testHeaders.value  = headersField.value;
  }

  // 1) Keep hidden inputs up-to-date as the user types in the visible fields
  baseUrlField.addEventListener('input', syncFields);
  pathField.addEventListener('input', syncFields);
  payloadTemplateField.addEventListener('input', syncFields);
  headersField.addEventListener('input', syncFields);

  // 2) Initialize hidden inputs on page load, before any typing occurs
  syncFields();
});
