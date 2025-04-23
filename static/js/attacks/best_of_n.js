$(document).ready(function(){
    var eventSource = null; // Keep track of the EventSource connection

    function fetchEndpointDetails(endpointId) {
      const detailsContainer = $('#endpoint_details');
      const formGroups = detailsContainer.find('.form-group'); // Get the hidden form groups
      const placeholder = detailsContainer.find('.blink');

      // Get the base URL from the select element's data attribute
      const baseUrl = $('#registered_endpoint').data('details-url-base');

      if (!baseUrl) { // Add a check
          console.error("Endpoint details URL base is missing from the select element!");
          alert("Configuration error: Cannot determine endpoint details URL.");
          return;
      }

      if (endpointId) {
        placeholder.hide(); // Hide placeholder text

        // Replace the dummy integer string with the actual ID
        const finalUrl = baseUrl.replace('999999', endpointId); 

        $.ajax({
          url: finalUrl, // Use the correctly constructed URL
          method: 'GET',
          success: function(data) {
            // Populate editable fields
            $('#ep_name_input').val(data.name);
            $('#ep_hostname_input').val(data.hostname);
            $('#ep_endpoint_input').val(data.endpoint);
            $('#ep_payload_input').val(data.http_payload);
            formGroups.slideDown(); // Show the form groups smoothly
          },
          error: function() {
            detailsContainer.html('<p class="error-message">Error fetching endpoint details.</p>'); // Show error
          }
        });
      } else {
        formGroups.slideUp(); // Hide form groups
        placeholder.show(); // Show placeholder
        // Optionally clear the inputs
         $('#ep_name_input').val('');
         $('#ep_hostname_input').val('');
         $('#ep_endpoint_input').val('');
         $('#ep_payload_input').val('');
      }
    }

    // When a new endpoint is selected from the dropdown, fetch its details.
    $('#registered_endpoint').change(function(){
      var epId = $(this).val();
      fetchEndpointDetails(epId);
    });

    // Function to close existing EventSource if any
    function closeEventSource() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
            console.log("EventSource closed.");
        }
    }

    // Before form submission, update the hidden inputs and start EventSource.
    $('#best-of-n-form').on('submit', function(e){
      e.preventDefault(); // Prevent default form submission

      // Close any existing connection first
      closeEventSource();

      // --- Validation (Optional but Recommended) ---
      if (!$('#registered_endpoint').val()) {
         alert('Please select a registered endpoint.');
         return;
      }
      if (!$('#initial_prompt').val().trim()) {
         alert('Please enter an initial prompt.');
         return;
      }
       if (!$('input[name="rearrange"], input[name="capitalization"], input[name="substitute"], input[name="typo"]').is(':checked')) {
          alert('Please select at least one permutation option.');
          return;
       }
      // --- End Validation ---


      // Copy the current values from the right-card inputs into the hidden fields.
      $('#hidden_ep_name').val($('#ep_name_input').val());
      $('#hidden_ep_hostname').val($('#ep_hostname_input').val());
      $('#hidden_ep_endpoint').val($('#ep_endpoint_input').val());
      $('#hidden_ep_payload').val($('#ep_payload_input').val());

      // --- UI Feedback: Start ---
      $('#loading-status-text').text('Initiating Best of N...'); // Initial status
      $('#loading-indicator').fadeIn();
      $('#chat_log').html(''); // Clear previous log
      $(this).find('button[type="submit"]').prop('disabled', true).css('opacity', 0.5); // Disable button
      // --- UI Feedback: End ---

      var formData = $(this).serialize();
      var actionUrl = $(this).data('action-url'); // Get URL from data attribute
      if (!actionUrl) { // Add a check in case the attribute is missing
          console.error("Form action URL is missing!");
          alert("Configuration error: Cannot determine submission URL.");
          return; 
      }
      var url = actionUrl + "?" + formData; 

      console.log("Connecting to EventSource:", url);
      eventSource = new EventSource(url); // Assign to the global variable

      eventSource.onopen = function() {
         console.log("EventSource connection opened.");
         $('#loading-status-text').text('Connection established...');
      };

      eventSource.onmessage = function(event) {
        console.log("Received data:", event.data);
        var data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.error("Failed to parse JSON:", event.data, e);
            // Optionally display an error in the chat log or status
             $('#chat_log').append('<div class="chat-row left"><div class="chat-bubble error"><strong>Error:</strong> Invalid data received from server.</div></div>');
            return; // Stop processing this message
        }


        // --- Check for Status Updates (Backend Dependent) ---
        if (data.status) {
           $('#loading-status-text').text(data.status);
           return; // Don't process as a chat message if it's just a status
        }
        // --- End Status Update Check ---


        // If the final event, show a final message and close.
        if (data.final) {
           var finalMsg = `Process completed. Best result from ${data.attempts_log ? data.attempts_log.length : 'N/A'} attempts.`;
           if(data.best_prompt && data.best_response) {
               finalMsg += `<br><br><strong>Best Prompt:</strong><pre>${data.best_prompt}</pre><strong>Best Response:</strong><pre>${data.best_response}</pre>`;
           }
           $('#chat_log').append(`<div class="chat-row left"><div class="chat-bubble final-message">${finalMsg}</div></div>`);
           closeEventSource(); // Close the connection
           // --- UI Feedback: Finish ---
           $('#loading-indicator').fadeOut();
           $('#best-of-n-form button[type="submit"]').prop('disabled', false).css('opacity', 1); // Re-enable button
           // --- UI Feedback: End Finish ---
          return;
        }

        // Otherwise, append the sent and received pair.
        var chatHtml = "";
         // Check if prompt and response exist to prevent errors
        if (data.prompt !== undefined) {
            chatHtml += '<div class="chat-row left"><div class="chat-bubble"><strong>Sent (Prompt):</strong><pre>' + escapeHtml(data.prompt) + '</pre></div></div>';
        }
        if (data.response !== undefined) {
             chatHtml += '<div class="chat-row right"><div class="chat-bubble"><strong>Received (Response):</strong><pre>' + escapeHtml(data.response) + '</pre></div></div>';
        }

        if (chatHtml) { // Only append if there's content
             const newEntry = $(chatHtml).appendTo('#chat_log');
             // Optional: Scroll to the bottom
             $('#chat_log').scrollTop($('#chat_log')[0].scrollHeight);
        }
      };

      eventSource.onerror = function(err) {
        console.error("EventSource failed:", err);
        $('#chat_log').append('<p class="error-message">Error connecting to or receiving data from the server. Connection closed.</p>');
        closeEventSource(); // Ensure connection is closed on error
        // --- UI Feedback: Error ---
        $('#loading-indicator').fadeOut();
        $('#loading-status-text').text('Error!'); // Optional: Show error in indicator before fading
        $('#best-of-n-form button[type="submit"]').prop('disabled', false).css('opacity', 1); // Re-enable button
        // --- UI Feedback: End Error ---
      };

      // No need to return false here as we used e.preventDefault()
    });

     // Helper function to escape HTML for display in <pre> tags
     function escapeHtml(unsafe) {
         if (typeof unsafe !== 'string') return unsafe; // Return non-strings as-is
         return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
     }

     // Initial check in case an endpoint is pre-selected or restored by the browser
     if ($('#registered_endpoint').val()) {
        fetchEndpointDetails($('#registered_endpoint').val());
     }

  });