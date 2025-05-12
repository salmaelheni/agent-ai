// static/js/script.js

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('recommendation-form');
    const titleInput = document.getElementById('job-title');
    const scrapeCheckbox = document.getElementById('scrape-new');
    const resultsDiv = document.getElementById('results');
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorMessageDiv = document.getElementById('error-message');
    const submitButton = document.getElementById('submit-button');

    form.addEventListener('submit', async (event) => {
        event.preventDefault(); // Empêche le rechargement de la page

        const jobTitle = titleInput.value.trim();
        const scrapeNew = scrapeCheckbox.checked;

        if (!jobTitle) {
            showError("Veuillez entrer un titre de poste.");
            return;
        }

        // Afficher le chargement et désactiver le bouton
        showLoading(true);
        hideError();
        submitButton.disabled = true;
        resultsDiv.innerHTML = ''; // Vider les anciens résultats

        try {
            // Appel à l'API Flask
            const response = await fetch('/api/recommend', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    title: jobTitle, 
                    scrape_new: scrapeNew 
                }),
            });

            showLoading(false); // Cacher le chargement dès la réponse
            const data = await response.json();

            if (!response.ok) {
                // Gérer les erreurs HTTP venant de Flask (ex: 400, 500)
                throw new Error(data.error || `Erreur HTTP ${response.status}`);
            }

            // Afficher les résultats
            displayResults(data.recommendations);

        } catch (error) {
            console.error("Erreur lors de la requête:", error);
            showError(`Erreur: ${error.message}`);
            showLoading(false); // S'assurer que le chargement est caché en cas d'erreur
        } finally {
             submitButton.disabled = false; // Réactiver le bouton
        }
    });

    function displayResults(recommendations) {
        resultsDiv.innerHTML = ''; // Vider à nouveau au cas où

        if (!recommendations || recommendations.length === 0) {
            resultsDiv.innerHTML = '<p>Aucune offre similaire trouvée.</p>';
            return;
        }

        recommendations.forEach(job => {
            const card = document.createElement('div');
            card.className = 'recommendation-card';

            const title = document.createElement('h3');
            title.textContent = job.title || 'Titre non disponible';

            const company = document.createElement('p');
            company.innerHTML = `<strong>Entreprise:</strong> ${job.company || 'N/A'}`;

            const location = document.createElement('p');
            location.innerHTML = `<strong>Lieu:</strong> ${job.location || 'N/A'}`;

            const score = document.createElement('p');
            score.innerHTML = `<strong>Score Similarité Titre:</strong> ${job.score !== undefined ? job.score.toFixed(4) : 'N/A'}`;
            
            const urlPara = document.createElement('p');
            const urlLink = document.createElement('a');
            urlLink.href = job.url || '#';
            urlLink.textContent = job.url || 'URL non disponible';
            urlLink.target = '_blank'; // Ouvrir dans un nouvel onglet
            urlLink.rel = 'noopener noreferrer';
            urlPara.innerHTML = `<strong>URL:</strong> `;
            urlPara.appendChild(urlLink);

            card.appendChild(title);
            card.appendChild(company);
            card.appendChild(location);
            card.appendChild(score);
            card.appendChild(urlPara);

            // Afficher les compétences (pour info)
            if (job.skills && job.skills.length > 0) {
                const skills = document.createElement('p');
                skills.className = 'skill-list';
                skills.innerHTML = `<strong>Compétences mentionnées:</strong> ${job.skills.join(', ')}`;
                card.appendChild(skills);
            }

            resultsDiv.appendChild(card);
        });
    }

    function showLoading(isLoading) {
        loadingIndicator.style.display = isLoading ? 'block' : 'none';
    }

    function showError(message) {
        errorMessageDiv.textContent = message;
        errorMessageDiv.style.display = 'block';
    }

    function hideError() {
        errorMessageDiv.style.display = 'none';
    }
});