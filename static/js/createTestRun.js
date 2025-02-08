// We'll store user-chosen suite info in JS to show in the left panel.
// On final submit, we create hidden inputs for them in the createRunForm.

const addSelectedBtn = document.getElementById("addSelectedBtn");
const suiteCheckboxes = document.querySelectorAll(".suite-checkbox");
const selectedSuitesList = document.getElementById("selectedSuitesList");
const hiddenSuitesContainer = document.getElementById("hiddenSuitesContainer");

// We'll keep an in-memory map of suiteID -> description
let selectedSuites = {};

// Load any existing from server if needed (not typical on first load).

addSelectedBtn.addEventListener("click", () => {
    // For each checked box, add to selectedSuites
    suiteCheckboxes.forEach(box => {
        if (box.checked) {
        const sid = box.value;
        const desc = box.dataset.description;
        selectedSuites[sid] = desc;
        box.checked = false; // uncheck after adding
        }
    });
    renderSelectedSuites();
});

function renderSelectedSuites() {
// Clear the UI
selectedSuitesList.innerHTML = "";
hiddenSuitesContainer.innerHTML = "";

// For each (id, desc) in selectedSuites, create an LI + hidden input
for (const [sid, desc] of Object.entries(selectedSuites)) {
        // create a list item
        const li = document.createElement("li");
        li.textContent = desc;
        selectedSuitesList.appendChild(li);

        // create a hidden <input name="suite_ids" value=sid>
        const hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = "suite_ids";
        hidden.value = sid;
        hiddenSuitesContainer.appendChild(hidden);
    }
}