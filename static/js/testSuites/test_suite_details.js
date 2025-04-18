/**
 * File: test_suite_details.js
 * Handles inline editing, add/remove/delete of cases, and filtering.
 */
document.addEventListener("DOMContentLoaded", () => {
    // Inline‑edit suite fields
    const editableFields = document.querySelectorAll(".editable");
    editableFields.forEach(field => {
      field.addEventListener("blur", async e => {
        const newValue = e.target.textContent.trim();
        const fieldName = e.target.dataset.field;
        const suiteId   = document
                           .querySelector(".test-suite-details")
                           .dataset.suiteId;
  
        try {
          let res = await fetch(`/test_suites/${suiteId}/update`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify({ [fieldName]: newValue })
          });
          if (!res.ok) throw new Error(`Failed to update ${fieldName}`);
          console.log(await res.json());
        } catch(err) {
          console.error(err);
          alert(`Error updating ${fieldName}`);
        }
      });
    });
  
    // Neon hover
    document.querySelectorAll(".btn").forEach(btn => btn.classList.add("neon-hover"));
  
    // Remove case from suite
    async function removeCase(caseId) {
      const suiteId = document.querySelector(".test-suite-details").dataset.suiteId;
      let res = await fetch(`/test_suites/${suiteId}/remove_test_case/${caseId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (!res.ok) throw new Error("Remove failed");
      await res.json();
      document.getElementById(`test-case-${caseId}`).remove();
    }
  
    // Delete case entirely
    async function deleteCase(caseId) {
      let res = await fetch(`/test_cases/${caseId}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" }
      });
      if (!res.ok) throw new Error("Delete failed");
      await res.json();
      document.getElementById(`test-case-${caseId}`).remove();
    }
  
    // Wire up existing remove / delete buttons
    document.querySelectorAll(".remove-btn").forEach(btn => {
      btn.addEventListener("click", e => {
        e.stopPropagation();
        if (confirm("Remove this case from suite?")) {
          removeCase(btn.dataset.caseId).catch(err => {
            console.error(err);
            alert("Error removing case");
          });
        }
      });
    });
    document.querySelectorAll(".delete-btn").forEach(btn => {
      btn.addEventListener("click", e => {
        e.stopPropagation();
        if (confirm("Delete this case forever?")) {
          deleteCase(btn.dataset.caseId).catch(err => {
            console.error(err);
            alert("Error deleting case");
          });
        }
      });
    });
  
    // Filter cases
    document.getElementById("promptFilter").addEventListener("input", e => {
      const filter = e.target.value.toLowerCase();
      document.querySelectorAll(".original-prompt").forEach(p => {
        const card = p.closest(".card");
        card.style.display = p.textContent.toLowerCase().includes(filter) ? "" : "none";
      });
    });
  
    // Add new case
    document.getElementById("add-test-case-form").addEventListener("submit", async e => {
      e.preventDefault();
      const btn = e.target.querySelector("button[type=submit]");
      btn.disabled = true;
      const orig = btn.textContent;
      btn.textContent = "Adding…";
  
      const suiteId = document.querySelector(".test-suite-details").dataset.suiteId;
      const prompt = document.getElementById("new-prompt").value.trim();
      try {
        let res  = await fetch(`/test_suites/${suiteId}/add_test_case`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
          },
          body: JSON.stringify({ prompt })
        });
        const json = await res.json();
        if (!json.success) throw new Error(json.error || "Add failed");
  
        const c = json.case;
        const cardHtml = `
          <div class="card mb-2" id="test-case-${c.id}">
            <div class="card-header" id="heading-${c.id}"
                 data-toggle="collapse"
                 data-target="#collapse-${c.id}"
                 aria-expanded="false"
                 aria-controls="collapse-${c.id}">
              <h5 class="mb-0">${c.prompt.substring(0,50)}…</h5>
            </div>
            <div id="collapse-${c.id}" class="collapse" data-parent="#accordion">
              <div class="card-body">
                <p class="original-prompt"><strong>Original Prompt:</strong> ${escapeHtml(c.prompt)}</p>
                <!-- other fields… -->
                <div class="mt-2">
                  <button class="btn btn-warning btn-sm remove-btn" data-case-id="${c.id}">
                    Remove from Suite
                  </button>
                  <button class="btn btn-danger btn-sm delete-btn" data-case-id="${c.id}">
                    Delete Test Case
                  </button>
                </div>
              </div>
            </div>
          </div>`;
        const container = document.getElementById("accordion");
        container.insertAdjacentHTML("afterbegin", cardHtml);
  
        // re-wire the new buttons
        container.querySelector(`.remove-btn[data-case-id="${c.id}"]`)
                 .addEventListener("click", e => {
                   e.stopPropagation();
                   removeCase(c.id).catch(err => alert("Error removing case"));
                 });
        container.querySelector(`.delete-btn[data-case-id="${c.id}"]`)
                 .addEventListener("click", e => {
                   e.stopPropagation();
                   deleteCase(c.id).catch(err => alert("Error deleting case"));
                 });
  
        document.getElementById("new-prompt").value = "";
      } catch(err) {
        console.error(err);
        alert(err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = orig;
      }
    });
  
    // HTML‑escape helper
    function escapeHtml(str) {
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }
  });
  