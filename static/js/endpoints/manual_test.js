/**
 * File: manual_test.js
 * Handles:
 *  • swapping payload templates
 *  • live transform previews (via transformerPreview.js)
 *  • insert‑token enforcement (via payload-token-enforcer.js)
 *  • AJAX form submission to prepend new history entries
 *  • history‑select → detail‑pane linkage
 */
document.addEventListener("DOMContentLoaded", () => {
  // 1) Template swap
  const tplSelect = document.getElementById("payloadTemplateSelect");
  const payloadEl = document.getElementById("http_payload");
  tplSelect.addEventListener("change", () => {
    try {
      const obj = JSON.parse(tplSelect.value);
      payloadEl.value = JSON.stringify(obj, null, 2);
    } catch (err) {
      console.error("Invalid template JSON", err);
    }
  });

  // 2) AJAX form submission
  const form = document.getElementById("manual-test-form");
  const accordion = document.getElementById("historyAccordion");
  const submitBtn = form.querySelector('button[type="submit"]');
  form.addEventListener("submit", async e => {
    e.preventDefault();
    submitBtn.disabled = true;
    const originalText = submitBtn.textContent;
    submitBtn.textContent = "Sending…";

    try {
      const res = await fetch(form.action, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body: new FormData(form)
      });
      const json = await res.json();
      if (!json.success) {
        throw new Error(json.error || "Unknown error");
      }

      const rec = json.record;
      const hdrId = `heading-${rec.id}`, colId = `collapse-${rec.id}`;
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="card-header" id="${hdrId}">
          <h5 class="mb-0">
            <button class="btn btn-link collapsed" type="button"
                    data-toggle="collapse"
                    data-target="#${colId}"
                    aria-expanded="false"
                    aria-controls="${colId}">
              ${rec.created_at}
            </button>
          </h5>
        </div>
        <div id="${colId}" class="collapse" aria-labelledby="${hdrId}" data-parent="#historyAccordion">
          <div class="card-body">
            <strong>Payload Sent:</strong>
            <pre class="code-block">${escapeHtml(rec.payload_sent)}</pre>
            <strong>Response:</strong>
            <pre class="code-block">${escapeHtml(rec.response_data)}</pre>
          </div>
        </div>`;
      accordion.prepend(card);

      // also add to history-select
      const sel = document.getElementById("history-select");
      const opt = document.createElement("option");
      opt.value = rec.id;
      opt.textContent = rec.created_at;
      opt.dataset.payload = rec.payload_sent;
      opt.dataset.response = rec.response_data;
      sel.prepend(opt);
      sel.value = rec.id;
      showRecord(rec.id);

    } catch (err) {
      console.error(err);
      alert("Error sending test: " + err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
    }
  });

  // 3) History selector → details pane
  const selectEl = document.getElementById("history-select");
  const detailPay = document.getElementById("detail-payload");
  const detailResp = document.getElementById("detail-response");

  function showRecord(id) {
    const rec = historyData[id];
    detailPay.textContent = rec.payload_sent;
    detailResp.textContent = rec.response_data;
  }

  selectEl.addEventListener("change", e => showRecord(e.target.value));
  showRecord(selectEl.value);

  // 4) HTML‑escape helper
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
});
