document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('scrape-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const spinner = submitBtn.querySelector('.spinner');
    
    const resultsContainer = document.getElementById('results-container');
    const resultsContent = document.getElementById('results-content');
    const sourcesBadge = document.getElementById('sources-badge');
    const apiKeyInput = document.getElementById('api-key');

    // Load API key from local storage
    const savedApiKey = localStorage.getItem('gemini_api_key');
    if (savedApiKey) {
        apiKeyInput.value = savedApiKey;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const apiKey = apiKeyInput.value.trim();
        const topic = document.getElementById('topic').value;
        const format = document.getElementById('format').value;

        // Save API key
        if (apiKey) {
            localStorage.setItem('gemini_api_key', apiKey);
        }

        // UI Loading State
        btnText.textContent = 'Extracting... (this takes a moment)';
        spinner.classList.remove('hidden');
        submitBtn.disabled = true;
        resultsContainer.classList.add('hidden');
        resultsContent.innerHTML = '';
        
        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ api_key: apiKey, topic, format })
            });

            let data;
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                data = await response.json();
            } else {
                const text = await response.text();
                throw new Error(`Server Error: ${text.substring(0, 300)}...`);
            }

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch data');
            }

            // Populate Results
            resultsContent.innerHTML = data.html;
            sourcesBadge.textContent = `${data.urls.length} Sources Analyzed`;
            
            // Show Results Panel
            resultsContainer.classList.remove('hidden');
            
            // Smooth scroll to results
            setTimeout(() => {
                resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);

        } catch (error) {
            resultsContent.innerHTML = `<div style="color: #ef4444; padding: 1rem; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; background: rgba(239, 68, 68, 0.1);">
                <strong>Error:</strong> ${error.message}
            </div>`;
            sourcesBadge.textContent = 'Failed';
            resultsContainer.classList.remove('hidden');
        } finally {
            // Restore UI
            btnText.textContent = 'Extract Data';
            spinner.classList.add('hidden');
            submitBtn.disabled = false;
        }
    });
});
