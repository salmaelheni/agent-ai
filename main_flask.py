# /mon_agent_reco_emploi/main_flask.py

import logging
from flask import Flask, render_template, request, jsonify
import json # Pour le retour JSON

# Importer les fonctions nécessaires de vos modules
from database_manager import load_job_offers_from_db, initialize_db
from duckduckgo_retriever import search_and_scrape_jobs
from recommender_engine import get_recommendations
# from scraper_utils import scrape_job_page # Non utilisé directement ici
# from text_processor import process_job_offer_text # Utilisé indirectement via recommender_engine

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialiser la base de données au démarrage (crée la table si besoin)
initialize_db()

# Créer l'application Flask
app = Flask(__name__)

# Route principale pour afficher l'interface utilisateur
@app.route('/')
def index():
    """Affiche la page HTML principale."""
    return render_template('index.html')

# Route API pour obtenir les recommandations
@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    """Point d'API pour obtenir des recommandations basées sur un titre."""
    try:
        data = request.get_json()
        if not data or 'title' not in data or not data['title'].strip():
            return jsonify({"error": "Le titre du poste est manquant."}), 400

        user_title = data['title'].strip()
        # La description est optionnelle et ignorée pour la similarité de titre
        user_description = data.get('description', '') 
        should_scrape = data.get('scrape_new', False) # Option pour lancer le scraping

        logging.info(f"Requête API reçue pour le titre : '{user_title}', Scraper nouvelles offres : {should_scrape}")

        if should_scrape:
            logging.info("Lancement du scraping de nouvelles offres...")
            try:
                # La recherche web se base sur le titre fourni
                search_query = f"offre emploi {user_title}" 
                new_jobs_count = search_and_scrape_jobs(search_query)
                logging.info(f"{new_jobs_count} nouvelles offres potentiellement ajoutées.")
            except Exception as e:
                logging.error(f"Erreur pendant le scraping : {e}")
                # On continue quand même pour essayer de recommander depuis la base existante
                # mais on pourrait retourner une erreur partielle si on voulait

        # Charger les offres (y compris les nouvelles si elles ont été scrappées)
        all_offers = load_job_offers_from_db()
        if not all_offers:
            logging.warning("La base de données est vide.")
            return jsonify({"error": "La base de données d'offres est vide.", "recommendations": []}), 200 # Retourner une liste vide

        # Obtenir les recommandations (basées sur le titre)
        recommendations = get_recommendations(user_title, user_description, all_offers)

        # Préparer les données pour le frontend (on ne renvoie pas l'embedding complet)
        results_for_frontend = []
        for reco in recommendations:
            results_for_frontend.append({
                "title": reco.get('original_title', 'N/A'),
                "company": reco.get('company', 'N/A'),
                "location": reco.get('location', 'N/A'),
                "url": reco.get('url', '#'),
                "score": round(reco.get('similarity_score_title', 0.0), 4), # Score de similarité du titre
                "skills": reco.get('skills', []) # Compétences pour info
            })

        logging.info(f"{len(results_for_frontend)} recommandations trouvées pour '{user_title}'")
        return jsonify({"recommendations": results_for_frontend})

    except Exception as e:
        logging.exception("Erreur inattendue dans l'API de recommandation.") # Log l'exception complète
        return jsonify({"error": "Une erreur interne est survenue."}), 500

if __name__ == '__main__':
    # Lance le serveur de développement Flask
    # accessible sur http://127.0.0.1:5000 par défaut
    logging.info("Lancement du serveur Flask...")
    app.run(debug=True) # debug=True pour le développement (recharge auto, plus d'infos d'erreur)
                        # Mettre debug=False en production