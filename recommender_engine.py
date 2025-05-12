# /mon_agent_reco_emploi/recommender_engine.py
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from text_processor import process_job_offer_text, get_text_embedding # get_text_embedding pour l'offre utilisateur
from database_manager import load_job_offers_from_db
from config import TOP_N_RECOMMENDATIONS
import logging
from scraper_utils import clean_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_recommendations(user_job_title: str, user_job_description: str, all_offers_in_db: list = None) -> list:
    """
    Recommande des offres d'emploi similaires UNIQUEMENT en se basant sur le titre.
    `user_job_description` est ignoré pour le calcul de similarité mais peut être utile
    pour l'extraction du titre si l'entrée utilisateur est une description complète.
    """
    if all_offers_in_db is None:
        all_offers_in_db = load_job_offers_from_db()

    if not all_offers_in_db:
        logging.warning("La base de données d'offres est vide. Aucune recommandation possible.")
        return []

    # 1. Traiter le TITRE de l'offre de l'utilisateur pour obtenir son embedding
    logging.info("Traitement du TITRE de l'offre de référence de l'utilisateur...")
    # Si user_job_title est vide mais user_job_description est fournie, on pourrait essayer d'en extraire un titre.
    # Pour l'instant, on suppose que user_job_title est le titre de référence.
    cleaned_user_title = clean_text(user_job_title) # Assurez-vous que text_processor a clean_text
    if not cleaned_user_title:
        logging.warning("Le titre de l'offre utilisateur est vide après nettoyage. Aucune recommandation possible.")
        return []
        
    user_title_embedding_np = get_text_embedding(cleaned_user_title)
    user_title_embedding = np.array(user_title_embedding_np, dtype=np.float32).reshape(1, -1)
    
    logging.debug(f"User title embedding shape: {user_title_embedding.shape}")

    # 2. Préparer les embeddings des titres des offres de la base
    db_title_embeddings_lists = []
    db_offers_data = [] 

    expected_embedding_dim = user_title_embedding.shape[1]

    for offer in all_offers_in_db:
        # Le champ 'embedding' dans la DB est maintenant supposé être l'embedding du titre
        if 'embedding' in offer and isinstance(offer['embedding'], list) and len(offer['embedding']) == expected_embedding_dim:
            db_title_embeddings_lists.append(offer['embedding'])
            db_offers_data.append(offer)
        else:
            actual_len = len(offer.get('embedding', [])) if isinstance(offer.get('embedding'), list) else 'N/A'
            logging.warning(
                f"Offre sans embedding de titre valide ou de dimension incorrecte ignorée : {offer.get('url', 'URL inconnue')}. "
                f"Dim attendue: {expected_embedding_dim}, Dim trouvée: {actual_len}"
            )
            
    if not db_offers_data:
        logging.warning("Aucune offre avec embedding de titre valide trouvée dans la base. Aucune recommandation possible.")
        return []

    try:
        db_title_embeddings_matrix = np.array(db_title_embeddings_lists, dtype=np.float32)
    except ValueError as e:
        logging.error(f"Erreur lors de la création de la matrice d'embeddings de titres de la BD : {e}")
        return []

    logging.debug(f"DB title embeddings matrix shape: {db_title_embeddings_matrix.shape}")

    if db_title_embeddings_matrix.ndim != 2 or db_title_embeddings_matrix.shape[1] != expected_embedding_dim:
        logging.error(
            f"Problème de forme avec db_title_embeddings_matrix. "
            f"Attendu: (N, {expected_embedding_dim}), Obtenu: {db_title_embeddings_matrix.shape}."
        )
        return []

    # 3. Calculer la similarité cosinus entre les embeddings de titres
    logging.info("Calcul des similarités cosinus sur les titres...")
    cosine_similarities_titles = cosine_similarity(user_title_embedding, db_title_embeddings_matrix)
    
    similarity_scores = cosine_similarities_titles[0]

    # 4. La combinaison de scores n'est plus nécessaire car on se base uniquement sur la similarité des titres.
    # Les `similarity_scores` sont maintenant nos scores finaux.
    for i, score in enumerate(similarity_scores):
        db_offers_data[i]['similarity_score_title'] = float(score) # Renommer pour plus de clarté
        # Supprimer les anciens champs de score si besoin, ou les laisser pour info si le dict le permet
        db_offers_data[i].pop('similarity_score_semantic', None)
        db_offers_data[i].pop('similarity_score_skills_jaccard', None)
        db_offers_data[i].pop('similarity_score_combined', None)


    # 5. Obtenir les indices des offres les plus similaires par titre
    sorted_indices = np.argsort(similarity_scores)[::-1]

    # 6. Préparer la liste des recommandations
    recommendations = []
    logging.info(f"Les {TOP_N_RECOMMENDATIONS} meilleures recommandations (basées sur la similarité des titres):")
    for i in range(min(TOP_N_RECOMMENDATIONS, len(sorted_indices))):
        idx = sorted_indices[i]
        recommended_offer = db_offers_data[idx]
        
        recommendations.append(recommended_offer)
        logging.info(
            f"  - Reco {i+1}: {recommended_offer.get('original_title', 'N/A')} "
            f"(URL: {recommended_offer.get('url', 'N/A')}) "
            f"Score Similarité Titre: {recommended_offer.get('similarity_score_title', 0.0):.4f}"
        )
        
    return recommendations

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG) # Voir les logs DEBUG

    test_db = load_job_offers_from_db()
    if not test_db:
        print("La base de données de test (offres_db.jsonl) est vide. Création d'une base factice pour le test.")
        # from text_processor import get_text_embedding # Déjà importé
        test_db = [
            {
                "url": "http://example.com/job_A", 
                "original_title": "Développeur Java Fullstack Senior", # Titre modifié pour test
                "cleaned_title": "developpeur java fullstack senior",
                "original_description": "Cherchons expert Java, Spring, Angular.",
                "embedding": get_text_embedding("Développeur Java Fullstack Senior").tolist(), # Embedding du titre
                "skills": ["java", "spring", "angular", "sql"],
                "company": "Tech Solutions", "location": "Paris"
            },
            {
                "url": "http://example.com/job_B",
                "original_title": "Ingénieur Python Backend",
                "cleaned_title": "ingenieur python backend",
                "original_description": "Nous recrutons un ingénieur backend Python, Django.",
                "embedding": get_text_embedding("Ingénieur Python Backend").tolist(), # Embedding du titre
                "skills": ["python", "django", "api rest", "docker"],
                "company": "Innovatech", "location": "Remote"
            },
            {
                "url": "http://example.com/job_C_python_data",
                "original_title": "Data Scientist Python Confirmé", # Titre modifié
                "cleaned_title": "data scientist python confirme",
                "original_description": "Poste de Data Scientist avec Python, ML.",
                "embedding": get_text_embedding("Data Scientist Python Confirmé").tolist(), # Embedding du titre
                "skills": ["python", "machine learning", "sql"],
                "company": "Data Corp", "location": "Lyon"
            }
        ]
        print("Utilisation d'une base de données factice pour le test.")

    # Offre de référence de l'utilisateur (seul le titre est utilisé pour la similarité)
    user_title_ref = "Développeur Python Senior"
    user_desc_ref = "Peu importe pour la similarité, mais on le passe quand même."

    print(f"\nRecherche de recommandations pour le titre : '{user_title_ref}'")
    recommendations = get_recommendations(user_title_ref, user_desc_ref, all_offers_in_db=test_db)

    if recommendations:
        print(f"\nTop {len(recommendations)} recommandations trouvées :")
        for i, rec in enumerate(recommendations):
            print(f"  {i+1}. {rec.get('original_title')} @ {rec.get('company')}")
            print(f"     URL: {rec.get('url')}")
            print(f"     Score Similarité Titre: {rec.get('similarity_score_title', 0.0):.4f}")
            print(f"     Compétences (pour info): {rec.get('skills')}")
            print("-" * 20)
    else:
        print("Aucune recommandation trouvée.")