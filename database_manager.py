# /mon_agent_reco_emploi/database_manager.py
import json
import os
import logging
import sqlite3 # Vous utilisez déjà sqlite3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Utilisation des constantes que vous avez définies
DATA_DIR = "data"
DATABASE_PATH = os.path.join(DATA_DIR, "job_offers.sqlite3") # Assurez-vous que c'est le bon nom de fichier

# Importation de text_processor pour la signature de add_job_offer_to_db si besoin,
# mais il est déjà importé globalement dans le fichier que vous avez montré.
from text_processor import process_job_offer_text

def ensure_data_dir_exists():
    os.makedirs(DATA_DIR, exist_ok=True)

def initialize_db():
    """Create the SQLite database and table if they don't exist."""
    ensure_data_dir_exists()
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    # Le schéma que vous avez fourni
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_offers (
            url TEXT PRIMARY KEY,
            original_title TEXT,
            original_description TEXT,
            company TEXT,
            location TEXT,
            cleaned_title TEXT,
            cleaned_description TEXT,
            combined_text_for_embedding TEXT,
            skills TEXT, -- Stocké comme JSON string
            embedding TEXT -- Stocké comme JSON string
        )
    ''')
    conn.commit()
    conn.close()

def load_job_offers_from_db() -> list:
    """Load all job offers from the SQLite database and parse JSON fields."""
    initialize_db() # S'assure que la table existe
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row # Permet d'accéder aux colonnes par leur nom
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_offers")
    rows = cursor.fetchall()
    conn.close()
    
    offers_list = []
    for row in rows:
        offer_dict = dict(row) # Convertit sqlite3.Row en dictionnaire Python
        
        # Désérialiser les champs JSON (embedding et skills)
        try:
            if offer_dict.get('embedding') is not None: # Vérifier si la chaîne n'est pas None
                offer_dict['embedding'] = json.loads(offer_dict['embedding'])
            else:
                # Gérer le cas où l'embedding est explicitement NULL dans la BD
                # ou si la colonne n'a pas été remplie pour une raison quelconque.
                offer_dict['embedding'] = None # ou une liste vide: [] si c'est plus logique en aval
        except (json.JSONDecodeError, TypeError) as e:
            logging.error(f"Erreur de désérialisation JSON pour l'embedding de l'offre {offer_dict.get('url', 'URL inconnue')}: {e}. Valeur brute: '{offer_dict.get('embedding')}'")
            offer_dict['embedding'] = None # Mettre à None en cas d'erreur pour que le filtrage le rejette proprement

        try:
            if offer_dict.get('skills') is not None: # Vérifier si la chaîne n'est pas None
                offer_dict['skills'] = json.loads(offer_dict['skills'])
            else:
                offer_dict['skills'] = [] # Les compétences peuvent être une liste vide par défaut
        except (json.JSONDecodeError, TypeError) as e:
            logging.error(f"Erreur de désérialisation JSON pour les skills de l'offre {offer_dict.get('url', 'URL inconnue')}: {e}. Valeur brute: '{offer_dict.get('skills')}'")
            offer_dict['skills'] = [] # Fallback à une liste vide
            
        offers_list.append(offer_dict)
        
    return offers_list

def add_job_offer_to_db(new_offer_data: dict, existing_offers: list = None) -> bool: 
    # existing_offers n'est plus vraiment utilisé avec SQLite de cette manière,
    # la vérification de doublon se fait via requête SQL.
    # On pourrait enlever `existing_offers` de la signature si elle n'est pas utilisée ailleurs.
    """
    Add a new job offer to the SQLite database if it doesn't already exist.
    Returns True if added, False if duplicate or invalid.
    """
    initialize_db() # S'assure que la table existe
    
    # Récupérer les infos de base pour le traitement
    url_to_add = new_offer_data.get("url")
    if not url_to_add:
        logging.warning("Tentative d'ajout d'une offre sans URL. Ignorée.")
        return False

    title = new_offer_data.get("title", "Titre non fourni")
    description = new_offer_data.get("description_full", "Description non fournie")

    if title == "Erreur de scraping" or description == "Erreur de scraping":
        logging.warning(f"Tentative d'ajout d'une offre avec erreur de scraping ignorée: {url_to_add}")
        return False

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Check if offer already exists by URL
    cursor.execute("SELECT 1 FROM job_offers WHERE url = ?", (url_to_add,))
    if cursor.fetchone():
        logging.info(f"Offre déjà existante dans la base de données SQLite : {url_to_add}")
        conn.close()
        return False

    # Si l'offre n'existe pas, la traiter et l'ajouter
    processed = process_job_offer_text(title, description) # `processed` vient de text_processor.py

    try:
        cursor.execute("""
            INSERT INTO job_offers (
                url, original_title, original_description, company, location,
                cleaned_title, cleaned_description, combined_text_for_embedding,
                skills, embedding
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            url_to_add,
            title, # Titre original du scraping
            description, # Description originale du scraping
            new_offer_data.get("company", "Inconnue"),
            new_offer_data.get("location", "Inconnue"),
            processed["cleaned_title"],
            processed["cleaned_description"],
            processed["combined_text_for_embedding"], # Cette clé doit exister dans `processed`
            json.dumps(processed["skills"]),          # Sérialiser en chaîne JSON
            json.dumps(processed["embedding"]),       # Sérialiser en chaîne JSON
        ))
        conn.commit()
        logging.info(f"Nouvelle offre ajoutée à la base de données SQLite : {url_to_add}")
        return True
    except sqlite3.Error as e:
        logging.error(f"Erreur SQLite lors de l'ajout de l'offre {url_to_add}: {e}")
        return False
    except KeyError as e: # Au cas où une clé manquerait dans `processed`
        logging.error(f"Clé manquante dans les données traitées pour l'offre {url_to_add}: {e}")
        return False
    finally:
        conn.close()

# Si vous avez d'autres fonctions comme populate_initial_db, elles devront aussi être adaptées à SQLite.