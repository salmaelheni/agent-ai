# /mon_agent_reco_emploi/config.py

# Clé API pour Groq (REMPLACEZ PAR VOTRE VRAIE CLÉ)
# Vous pouvez l'obtenir sur https://console.groq.com/keys
GROQ_API_KEY = "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"  # IMPORTANT: Ne commitez pas votre vraie clé sur un dépôt public

# Modèle Groq à utiliser
GROQ_MODEL_NAME = "llama3-8b-8192" # ou "mixtral-8x7b-32768", "llama3-70b-8192" etc.

# Chemin vers la base de données des offres d'emploi
DATABASE_PATH = "data/offres_db.jsonl"

# Modèle Sentence Transformer à utiliser
# Pour le français et d'autres langues : 'paraphrase-multilingual-MiniLM-L12-v2'
# Pour l'anglais seulement, 'all-MiniLM-L6-v2' est plus léger et rapide.
SENTENCE_TRANSFORMER_MODEL = 'paraphrase-multilingual-MiniLM-L12-v2'

# Nombre maximum de résultats de recherche DuckDuckGo
DDG_MAX_RESULTS = 5

# Nombre de recommandations à retourner
TOP_N_RECOMMENDATIONS = 3

# Liste de compétences de base pour une extraction simplifiée (à enrichir considérablement)
# Ceci est un exemple très basique. Une approche plus robuste est nécessaire en production.
SKILLS_KEYWORDS = [
    "python", "java", "c++", "javascript", "react", "angular", "vue", "node.js",
    "django", "flask", "spring", "sql", "nosql", "mongodb", "postgresql",
    "docker", "kubernetes", "aws", "azure", "gcp", "git", "agile", "scrum",
    "machine learning", "deep learning", "data science", "nlp",
    "communication", "problem solving", "teamwork", "leadership",
    "gestion de projet", "analyse de données", "cybersécurité"
]

# Langue pour spaCy (utilisé pour le POS tagging ou NER si implémenté plus tard)
# Ex: "fr_core_news_sm" pour le français, "en_core_web_sm" pour l'anglais
SPACY_MODEL_LANG = "fr_core_news_sm"