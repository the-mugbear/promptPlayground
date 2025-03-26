// updateDisposition.js
// This script intercepts the change event on disposition dropdowns for test case records.
// Instead of submitting the form and reloading the page, an AJAX POST request is sent to update the status.

document.addEventListener("DOMContentLoaded", function() {
    // Select all forms responsible for updating execution status.
    // We assume that these forms have been given the class "update-status-form".
    const updateForms = document.querySelectorAll("form.update-status-form");
    
    updateForms.forEach(form => {
      // Find the select element within the form.
      const select = form.querySelector("select[name='status']");
      if (select) {
        // Attach a change event listener to intercept the default form submission.
        select.addEventListener("change", function(e) {
          // Prevent the default submission that would reload the page.
          e.preventDefault();
          
          // Create a FormData object from the form.
          const formData = new FormData(form);
          const url = form.action;
          
          // Optionally disable the select to prevent duplicate submissions.
          select.disabled = true;
          
          // Send an AJAX POST request with the form data.
          fetch(url, {
            method: "POST",
            body: formData,
            headers: {
              "X-Requested-With": "XMLHttpRequest"  // Allows the server to identify this as an AJAX request.
            }
          })
          .then(response => {
            if (!response.ok) {
              throw new Error("Network response was not ok");
            }
            // Assume the server returns JSON with updated status info.
            return response.json();
          })
          .then(data => {
            // Optionally update the UI if needed (for example, update a status label).
            console.log("Status updated successfully:", data);
            // Re-enable the select after successful update.
            select.disabled = false;
          })
          .catch(error => {
            console.error("Error updating status:", error);
            // Re-enable the select so the user can try again.
            select.disabled = false;
          });
        });
      }
    });
  });
  