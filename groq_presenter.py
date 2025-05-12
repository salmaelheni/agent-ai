# /mon_agent_reco_emploi/groq_presenter.py
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL_NAME
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not GROQ_API_KEY or GROQ_API_KEY == "VOTRE_CLE_API_GROQ":
    logging.warning("Clé API Groq non configurée dans config.py. Le module GroqPresenter ne fonctionnera pas.")
    client_groq = None
else:
    try:
        client_groq = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        logging.error(f"Erreur lors de l'initialisation du client Groq : {e}")
        client_groq = None

def format_recommendations_with_groq(user_job_input_summary: str, recommended_jobs: list) -> str:
    """
    Utilise l'API Groq pour formater et présenter les recommandations d'offres d'emploi,
    en soulignant que la similarité est basée sur les titres.
    """
    if not client_groq:
        logging.error("Client Groq non initialisé. Impossible de formater avec Groq.")
        # Fallback vers une présentation brute si Groq n'est pas configuré
        raw_output = "Le service de formatage IA n'est pas disponible. Voici les recommandations brutes (similarité par titre) :\n\n"
        if not recommended_jobs:
            return raw_output + "Aucune recommandation trouvée."
        for job in recommended_jobs:
            raw_output += (f"- Titre: {job.get('original_title', 'N/A')}\n"
                           f"  Entreprise: {job.get('company', 'N/A')}\n"
                           f"  Lieu: {job.get('location', 'N/A')}\n"
                           f"  Score Similarité Titre: {job.get('similarity_score_title', 0.0):.2f}\n"
                           f"  URL: {job.get('url', 'N/A')}\n\n")
        return raw_output

    if not recommended_jobs:
        return "Aucune offre à formater n'a été trouvée."

    prompt_parts = []
    prompt_parts.append(f"Bonjour ! Vous êtes un assistant expert en recrutement. Un utilisateur recherche un emploi.")
    # user_job_input_summary contient maintenant quelque chose comme "Titre de poste recherché : 'Développeur Python'"
    prompt_parts.append(f"L'utilisateur a spécifié le type de poste suivant : \"{user_job_input_summary}\".")
    prompt_parts.append("\nVoici quelques offres d'emploi dont les titres sont sémantiquement similaires à sa recherche. Pour chacune, j'indique le titre, l'entreprise, le lieu, l'URL, et quelques compétences clés de l'offre (à titre informatif, la similarité principale est sur le titre). J'inclus aussi un score de similarité de titre (plus il est élevé, mieux c'est, sur une échelle de -1 à 1 ou 0 à 1 selon le calcul).")

    for i, job in enumerate(recommended_jobs):
        title = job.get('original_title', 'Titre non disponible')
        company = job.get('company', 'Entreprise non spécifiée')
        location = job.get('location', 'Lieu non spécifié')
        url = job.get('url', '#')
        # Les compétences sont affichées pour information, même si elles ne participent plus au score principal
        skills_in_offer = ", ".join(job.get('skills', [])) if job.get('skills') else "Non spécifiées"
        score = job.get('similarity_score_title', 0.0) # Utilise le nouveau champ de score
        
        prompt_parts.append(
            f"\nOffre {i+1} :"
            f"\n  - Titre : {title}"
            f"\n  - Entreprise : {company}"
            f"\n  - Lieu : {location}"
            f"\n  - Compétences mentionnées (pour info) : {skills_in_offer}"
            f"\n  - Score de similarité du titre : {score:.2f}" # Précision du score
            f"\n  - URL : {url}"
        )

    prompt_parts.append("\nPourriez-vous présenter ces offres de manière engageante et concise à l'utilisateur ?")
    prompt_parts.append("Mettez en avant la pertinence du titre de chaque offre par rapport à sa recherche initiale.")
    prompt_parts.append("Adoptez un ton amical et professionnel. Utilisez des listes à puces si cela rend la lecture plus facile.")
    prompt_parts.append("Terminez par une note positive l'encourageant à explorer ces pistes.")

    final_prompt = "\n".join(prompt_parts)
    logging.info(f"Prompt envoyé à Groq (début): {final_prompt[:300]}...")

    try:
        chat_completion = client_groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Vous êtes un assistant IA spécialisé dans la recommandation d'offres d'emploi. Vous soulignerez que les recommandations sont basées sur la similarité des titres des postes. Soyez concis, professionnel et engageant."
                },
                {
                    "role": "user",
                    "content": final_prompt,
                }
            ],
            model=GROQ_MODEL_NAME,
            temperature=0.6, # Un peu moins de créativité pour rester factuel
            max_tokens=1500, # Augmenté si besoin pour des listes plus longues
        )
        response_content = chat_completion.choices[0].message.content
        logging.info("Réponse reçue de Groq.")
        return response_content
    except Exception as e:
        logging.error(f"Erreur lors de l'appel à l'API Groq : {e}")
        # Fallback amélioré si Groq échoue
        fallback_response = "J'ai rencontré un souci en formatant les recommandations avec l'assistant IA. Voici néanmoins les offres trouvées, basées sur la similarité des titres :\n\n"
        for job in recommended_jobs:
            fallback_response += (f"- Titre: {job.get('original_title', 'N/A')} (Score: {job.get('similarity_score_title', 0.0):.2f})\n"
                                  f"  Entreprise: {job.get('company', 'N/A')}, Lieu: {job.get('location', 'N/A')}\n"
                                  f"  URL: {job.get('url', 'N/A')}\n\n")
        return fallback_response

if __name__ == '__main__':
    if not client_groq:
        print("Le client Groq n'est pas initialisé (vérifiez la clé API dans config.py). Test annulé.")
    else:
        sample_user_input_summary = "Titre de poste recherché : \"Développeur Fullstack Expérimenté\""
        sample_reco_jobs = [
            {
                'original_title': 'Développeur Fullstack Senior (Python/React)', 
                'company': 'Tech Pionniers SA', 
                'location': 'Paris (Flexible)', 
                'url': 'http://example.com/job1', 
                'skills': ['python', 'react', 'django', 'api'],
                'similarity_score_title': 0.88 # Nouveau nom de score
            },
            {
                'original_title': 'Lead Développeur Fullstack (Java/Angular)', 
                'company': 'Solutions Digitales Corp', 
                'location': 'Lyon', 
                'url': 'http://example.com/job2', 
                'skills': ['java', 'angular', 'spring boot', 'microservices'],
                'similarity_score_title': 0.75 # Nouveau nom de score
            }
        ]
        
        print("Formatage des recommandations avec Groq (basé sur similarité de titres)...")
        formatted_output = format_recommendations_with_groq(sample_user_input_summary, sample_reco_jobs)
        print("\n--- Réponse de Groq ---")
        print(formatted_output)
        print("--- Fin de la réponse ---")