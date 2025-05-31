document.addEventListener('DOMContentLoaded', function () {
    const addPromptBtn = document.getElementById('addPromptBtn');
    const newPromptTextarea = document.getElementById('new_prompt_text');
    const addedTestCasesContainer = document.getElementById('addedTestCasesContainer');
    const createSuiteForm = document.getElementById('create-suite-form');
    const hiddenPromptsInput = document.getElementById('test_case_prompts');
    const noPromptsMessage = document.getElementById('noPromptsMessage');

    let prompts = []; // Array to store the text of added prompts

    // Function to update the display of added prompts
    function renderPrompts() {
        // Clear current display
        addedTestCasesContainer.innerHTML = ''; 

        if (prompts.length === 0) {
            if (noPromptsMessage) { 
                addedTestCasesContainer.appendChild(noPromptsMessage);
                noPromptsMessage.style.display = 'block';
            }
        } else {
            if (noPromptsMessage) {
                noPromptsMessage.style.display = 'none'; // Hide "no prompts" message
            }
            prompts.forEach((promptText, index) => {
                const promptCard = document.createElement('div');
                promptCard.classList.add('added-prompt-card');

                const textElement = document.createElement('p');
                // To preserve whitespace and show line breaks within a single prompt if any:
                textElement.style.whiteSpace = 'pre-wrap'; 
                textElement.textContent = promptText;
                
                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.textContent = 'Remove';
                removeBtn.classList.add('remove-prompt-btn');
                removeBtn.dataset.index = index;

                removeBtn.addEventListener('click', function () {
                    prompts.splice(this.dataset.index, 1);
                    renderPrompts();
                });

                promptCard.appendChild(textElement);
                promptCard.appendChild(removeBtn);
                addedTestCasesContainer.appendChild(promptCard);
            });
        }
        hiddenPromptsInput.value = JSON.stringify(prompts);
    }

    // Event listener for the "Add Prompt" button (MODIFIED FOR BULK ADD)
    if (addPromptBtn) {
        addPromptBtn.addEventListener('click', function () {
            const allPromptsText = newPromptTextarea.value.trim();
            if (allPromptsText) {
                // Split the textarea content by new lines
                const lines = allPromptsText.split('\n');
                let addedCount = 0;
                lines.forEach(line => {
                    const promptValue = line.trim();
                    if (promptValue) { // Ensure the line is not empty after trimming
                        prompts.push(promptValue);
                        addedCount++;
                    }
                });

                if (addedCount > 0) {
                    newPromptTextarea.value = ''; // Clear the textarea
                    renderPrompts();
                } else {
                    alert('Please enter valid prompt text. Empty lines will be ignored.');
                }
            } else {
                alert('Please enter some text for the prompt(s).');
            }
        });
    }

    if (createSuiteForm) {
        createSuiteForm.addEventListener('submit', function (event) {
            hiddenPromptsInput.value = JSON.stringify(prompts);
            // Optional: Add validation to ensure at least one prompt is added if required
            // if (prompts.length === 0) {
            //   alert('Please add at least one test case prompt.');
            //   event.preventDefault(); // Stop form submission
            // }
        });
    }

    renderPrompts(); 
});