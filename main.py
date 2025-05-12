# /mon_agent_reco_emploi/main.py
import logging
from database_manager import load_job_offers_from_db # add_job_offer_to_db n'est pas directement utilisé ici
from duckduckgo_retriever import search_and_scrape_jobs
from recommender_engine import get_recommendations
from groq_presenter import format_recommendations_with_groq
from text_processor import process_job_offer_text # Utilisé pour traiter l'offre utilisateur si besoin pour le titre
from scraper_utils import scrape_job_page # Si l'utilisateur donne une URL
from config import GROQ_API_KEY # Pour vérifier si Groq est configuré

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_user_job_preference():
    """Récupère la préférence de l'utilisateur (URL ou description textuelle)."""
    while True:
        choice = input("Souhaitez-vous fournir une offre d'emploi via (1) URL ou (2) Description textuelle ? Entrez 1 ou 2 : ").strip()
        if choice == '1':
            url = input("Veuillez coller l'URL de l'offre d'emploi qui vous plaît : ").strip()
            if url:
                return {"type": "url", "content": url}
            else:
                print("URL non valide.")
        elif choice == '2':
            title = input("Quel est le titre du poste qui vous intéresse ? (Ce titre sera utilisé pour la similarité) : ").strip()
            description = input("Veuillez décrire brièvement le type de poste (cette description n'affectera pas la similarité) : ").strip()
            if title: # Le titre est maintenant le plus important
                return {"type": "text", "content": {"title": title, "description": description}}
            else:
                print("Le titre est requis.")
        else:
            print("Choix invalide. Veuillez entrer 1 ou 2.")

def process_user_preference(preference: dict) -> dict:
    """Traite la préférence de l'utilisateur pour obtenir titre et description."""
    if preference["type"] == "url":
        logging.info(f"Scraping de l'URL fournie par l'utilisateur : {preference['content']}")
        scraped_data = scrape_job_page(preference["content"])
        if scraped_data and scraped_data.get("title") != "Erreur de scraping":
            # La description scrappée est gardée pour contexte mais seul le titre importe pour la similarité
            return {"title": scraped_data["title"], "description": scraped_data["description_full"]}
        else:
            logging.error("Impossible de scraper l'URL fournie par l'utilisateur.")
            return None
    elif preference["type"] == "text":
        return preference["content"]
    return None


def run_agent():
    """Fonction principale pour exécuter l'agent de recommandation."""
    logging.info(" démarrage de l'agent de recommandation d'offres d'emploi...")

    if not GROQ_API_KEY or GROQ_API_KEY == "VOTRE_CLE_API_GROQ":
        logging.warning("ATTENTION : La clé API Groq n'est pas configurée dans config.py.")
        logging.warning("Les recommandations seront brutes et non formatées par l'IA.")
        print("\nATTENTION : La clé API Groq n'est pas configurée. Les résultats seront moins présentables.\n")

    user_pref = get_user_job_preference()
    if not user_pref:
        logging.error("Aucune préférence utilisateur fournie. Arrêt.")
        return

    user_job_details = process_user_preference(user_pref)
    if not user_job_details or not user_job_details.get("title"): # S'assurer qu'on a un titre
        logging.error("Impossible de traiter la préférence utilisateur ou titre manquant. Arrêt.")
        print("Désolé, un titre d'offre est nécessaire pour la recherche.")
        return
        
    user_title = user_job_details["title"]
    user_description = user_job_details.get("description", "") # La description est optionnelle pour la logique de similarité
    
    logging.info(f"Offre de référence : Titre='{user_title}' (La similarité sera basée sur ce titre).")
    
    # Recherche DuckDuckGo simplifiée, basée principalement sur le titre
    search_query = f"offre emploi {user_title}" 

    update_db_choice = input(f"\nVoulez-vous rechercher de nouvelles offres en ligne basées sur le titre '{user_title}' et mettre à jour la base (o/n) ? ").strip().lower()
    if update_db_choice == 'o':
        logging.info(f"Recherche de nouvelles offres avec la requête : {search_query}")
        new_jobs_found = search_and_scrape_jobs(search_query)
        logging.info(f"{new_jobs_found} nouvelles offres potentiellement ajoutées à la base de données.")
    else:
        logging.info("Skipping de la mise à jour de la base de données depuis le web.")

    all_offers = load_job_offers_from_db()
    if not all_offers:
        logging.error("La base de données d'offres est vide et aucune nouvelle offre n'a été ajoutée. Impossible de recommander.")
        print("Désolé, la base de données d'offres est vide. Essayez de la peupler ou d'activer la recherche en ligne.")
        return

    logging.info("Génération des recommandations basées sur la similarité des titres...")
    # On passe user_description pour maintenir la signature de la fonction, mais elle n'est pas utilisée
    # pour le calcul de similarité dans la version actuelle de recommender_engine.py
    recommendations = get_recommendations(user_title, user_description, all_offers) 

    if not recommendations:
        logging.info("Aucune recommandation trouvée pour ce titre.")
        print("\nDésolé, je n'ai pas trouvé d'offres avec des titres suffisamment similaires pour le moment.")
        return

    logging.info("Formatage des recommandations...")
    # Le résumé pour Groq se concentre sur le titre recherché
    user_input_summary_for_groq = f"Titre de poste recherché : \"{user_title}\"" 
    
    formatted_presentation = format_recommendations_with_groq(user_input_summary_for_groq, recommendations)
    
    print("\n--- Vos Recommandations Personnalisées (basées sur la similarité des titres) ---")
    print(formatted_presentation)
    print("--- Fin des Recommandations ---")
    logging.info("Agent de recommandation terminé.")

if __name__ == '__main__':
    # Pour des tests, il peut être utile de passer le niveau de log en DEBUG
    # logging.getLogger().setLevel(logging.DEBUG) 
    run_agent()