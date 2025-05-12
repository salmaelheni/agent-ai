# /mon_agent_reco_emploi/text_processor.py
import re
import spacy
from sentence_transformers import SentenceTransformer
from config import SENTENCE_TRANSFORMER_MODEL, SKILLS_KEYWORDS, SPACY_MODEL_LANG
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    nlp = spacy.load(SPACY_MODEL_LANG)
except OSError:
    logging.warning(f"Modèle spaCy {SPACY_MODEL_LANG} non trouvé. Certaines fonctionnalités NLP avancées (comme NER) seront limitées.")
    logging.warning(f"Essayez : python -m spacy download {SPACY_MODEL_LANG}")
    nlp = None

model_st = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)

def clean_text(text: str) -> str:
    """Nettoie le texte : supprime les caractères spéciaux, normalise les espaces."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\.\-,;:\'"()éèàêâûôîäëüöïç]', '', text, flags=re.UNICODE)
    text = text.strip()
    return text

def extract_skills_simple(text: str, skills_keywords: list = None) -> list:
    """
    Extraction de compétences (peut toujours être utile pour l'affichage ou le filtrage futur,
    mais ne sera pas utilisée pour le calcul de similarité principal).
    """
    if not text:
        return []
    
    if skills_keywords is None:
        skills_keywords = SKILLS_KEYWORDS

    found_skills = set()
    text_lower = text.lower()
    
    for skill in skills_keywords:
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found_skills.add(skill.strip().lower())
            
    return sorted(list(found_skills))


def get_text_embedding(text: str):
    """Génère un vecteur (embedding) pour un texte donné."""
    if not text:
        # Retourner un vecteur de zéros de la bonne dimension si le texte est vide
        # Cela garantit que l'embedding a toujours la même forme.
        return model_st.encode("") 
    return model_st.encode(text)

def process_job_offer_text(title: str, description: str) -> dict:
    """
    Traite le texte d'une offre d'emploi.
    L'embedding principal ('embedding') est basé UNIQUEMENT sur le titre.
    'combined_text_for_embedding' est aussi fourni pour compatibilité avec la BDD.
    """
    cleaned_title = clean_text(title)
    cleaned_description = clean_text(description)
    
    # L'embedding utilisé pour la similarité est calculé SEULEMENT sur le titre nettoyé
    title_embedding = get_text_embedding(cleaned_title)
    
    # L'extraction de compétences peut toujours être faite sur la description pour information
    skills = extract_skills_simple(f"{cleaned_title}. {cleaned_description}")
    
    # Recréer le combined_text pour la compatibilité avec la base de données
    # Il peut être stocké mais ne sera pas activement utilisé pour la similarité des titres.
    combined_text_for_db = f"{cleaned_title}. {cleaned_title}. {cleaned_description}"

    return {
        "cleaned_title": cleaned_title,
        "cleaned_description": cleaned_description,
        "combined_text_for_embedding": combined_text_for_db, # CLÉ RÉINTRODUITE
        "skills": skills,
        "embedding": title_embedding.tolist() # IMPORTANT: 'embedding' est l'embedding du TITRE
    }

if __name__ == '__main__':
    sample_title = "Développeur Python Senior"
    sample_description = """
    Nous recherchons un Développeur Python expérimenté (H/F) pour rejoindre notre équipe dynamique.
    Vous travaillerez sur des projets innovants utilisant Django et Flask.
    Compétences requises : Python, Django, SQL. Connaissance de Docker est un plus.
    """
    
    processed_data = process_job_offer_text(sample_title, sample_description)
    print(f"Titre nettoyé: {processed_data['cleaned_title']}")
    print(f"Description (début): {processed_data['cleaned_description'][:100]}...")
    print(f"Combined text (pour DB): {processed_data['combined_text_for_embedding'][:100]}...")
    print(f"Compétences extraites: {processed_data['skills']}")
    print(f"Taille de l'embedding (basé sur le titre): {len(processed_data['embedding'])}")