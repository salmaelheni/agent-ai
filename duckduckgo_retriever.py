from duckduckgo_search import DDGS
from config import DDG_MAX_RESULTS
from scraper_utils import scrape_job_page, add_domain_rules
from database_manager import add_job_offer_to_db, load_job_offers_from_db
import logging
import re
import time
import random
from urllib.parse import urlparse

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Sites populaires à exclure car nécessitant une connexion ou compliqués à scraper
EXCLUDED_DOMAINS = [
    "indeed.com", "linkedin.com", "jooble.org", "glassdoor.fr",
    "pole-emploi.fr/connexion", "monster.fr/connexion", 
    "facebook.com", "twitter.com", "instagram.com", "youtube.com"
]

# Mots-clés qui indiquent qu'une URL est probablement une page d'offre d'emploi
JOB_URL_KEYWORDS = [
    "job", "emploi", "offre", "carriere", "recrutement", "poste", 
    "annonce", "vacancy", "position", "careers", "jobs"
]

def is_probably_job_url(url, title=None, snippet=None):
    """
    Détermine si une URL est probablement une page d'offre d'emploi
    en se basant sur l'URL, le titre et le snippet.
    """
    url_lower = url.lower()
    
    # Vérifier les mots-clés dans l'URL
    if any(keyword in url_lower for keyword in JOB_URL_KEYWORDS):
        return True
    
    # Vérifier les patterns communs d'URLs d'offres d'emploi
    job_patterns = [
        r'/jobs?/|/offer/|/offre[s]?/|/recruitment|/carriere[s]?/',
        r'/annonce[-_]emploi|/job[-_]description|/vacancies?/'
    ]
    if any(re.search(pattern, url_lower) for pattern in job_patterns):
        return True
    
    # Vérifier le titre et le snippet s'ils sont fournis
    if title:
        title_lower = title.lower()
        if any(keyword in title_lower for keyword in ['job', 'emploi', 'poste', 'cddi', 'recrutement']):
            return True
    
    if snippet:
        snippet_lower = snippet.lower()
        job_indicators = ['nous recherchons', 'we are looking for', 'offre d\'emploi', 
                         'job description', 'votre mission', 'your mission']
        if any(indicator in snippet_lower for indicator in job_indicators):
            return True
    
    return False

def format_search_query(job_title=None, skills=None, location=None, experience=None):
    """
    Formate une requête de recherche optimisée pour trouver des offres d'emploi.
    """
    query_parts = []
    
    # Ajouter le mot-clé principal pour trouver des offres d'emploi
    query_parts.append("offre emploi")
    
    # Ajouter le titre du poste s'il est fourni
    if job_title:
        query_parts.append(job_title)
    
    # Ajouter les compétences s'il y en a
    if skills and isinstance(skills, list) and len(skills) > 0:
        # Limiter à 3 compétences pour ne pas trop restreindre
        selected_skills = skills[:3]
        query_parts.extend(selected_skills)
    
    # Ajouter la localisation si fournie
    if location:
        query_parts.append(location)
    
    # Ajouter l'expérience si fournie
    if experience:
        query_parts.append(experience)
    
    # Joindre toutes les parties avec des espaces
    query = " ".join(query_parts)
    
    return query

def extract_domain(url):
    """Extrait le domaine principal d'une URL"""
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        # Obtenir le domaine principal (ex: example.com à partir de subdomain.example.com)
        parts = domain.split('.')
        if len(parts) > 2:
            domain = '.'.join(parts[-2:])
        return domain
    except:
        return None

def search_and_scrape_jobs(query=None, job_title=None, skills=None, location=None, 
                          experience=None, region="fr-fr", max_results=None):
    """
    Recherche des offres d'emploi sur DuckDuckGo, les scrape, et les ajoute à la DB.
    Peut prendre soit une requête directe, soit des composants pour construire la requête.
    Retourne le nombre de nouvelles offres ajoutées.
    """
    # Si aucune requête directe n'est fournie, en construire une
    if not query:
        query = format_search_query(job_title, skills, location, experience)
    
    # Utiliser la limite configurée si max_results n'est pas spécifié
    if max_results is None:
        max_results = DDG_MAX_RESULTS
    
    logging.info(f"Lancement de la recherche DuckDuckGo pour : '{query}'")
    urls_to_scrape = []
    urls_by_domain = {}  # Pour suivre combien d'URLs de chaque domaine
    
    try:
        with DDGS() as ddgs:
            search_results = list(ddgs.text(keywords=query, region=region, max_results=max_results))
            
        logging.info(f"{len(search_results)} résultats trouvés sur DuckDuckGo.")
        
        for result in search_results:
            if not result or 'href' not in result:
                continue
                
            url = result['href']
            title = result.get('title', '')
            snippet = result.get('body', '')
            
            # Vérifier si le domaine est exclu
            domain = extract_domain(url)
            if domain and any(excluded in domain for excluded in EXCLUDED_DOMAINS):
                continue
            
            # Limiter le nombre d'URLs par domaine pour diversifier les sources
            if domain:
                if domain in urls_by_domain and urls_by_domain[domain] >= 3:
                    continue  # Déjà 3 URLs de ce domaine, passer
                urls_by_domain[domain] = urls_by_domain.get(domain, 0) + 1
            
            # Vérifier si l'URL semble être une offre d'emploi
            if is_probably_job_url(url, title, snippet):
                urls_to_scrape.append({
                    'url': url,
                    'domain': domain,
                    'title': title,
                    'snippet': snippet
                })
        
        logging.info(f"{len(urls_to_scrape)} URLs potentiellement pertinentes identifiées.")
        
        if not urls_to_scrape:
            logging.warning("Aucune URL d'offre d'emploi trouvée pour cette requête.")
            return 0

    except Exception as e:
        logging.error(f"Erreur durant la recherche DuckDuckGo : {e}")
        return 0

    # Charger les offres existantes pour éviter les doublons
    current_offers_in_db = load_job_offers_from_db()
    new_offers_added_count = 0
    
    # Trier les URLs par domaine pour regrouper les scraping par site
    urls_to_scrape.sort(key=lambda x: x['domain'] if x['domain'] else '')
    
    for i, url_info in enumerate(urls_to_scrape):
        url = url_info['url']
        domain = url_info['domain']
        
        logging.info(f"Traitement de l'URL {i+1}/{len(urls_to_scrape)}: {url}")
        
        # Vérifier si l'URL est déjà dans la base
        if any(offer.get('url') == url for offer in current_offers_in_db):
            logging.info(f"URL déjà présente dans la base de données. Ignorée.")
            continue
        
        # Ajouter un délai aléatoire entre les requêtes pour éviter d'être bloqué
        if i > 0:
            time.sleep(random.uniform(2, 5))
        
        # Scraper l'URL
        scraped_data = scrape_job_page(url)
        
        # Vérifier si le scraping a réussi
        if scraped_data and scraped_data.get("title") != "Erreur de scraping":
            # Si nous avons des infos de titre/snippet de DuckDuckGo, les utiliser si besoin
            if scraped_data.get("title") == "Titre non trouvé" and url_info.get('title'):
                scraped_data["title"] = url_info['title']
            
            if add_job_offer_to_db(scraped_data, current_offers_in_db):
                new_offers_added_count += 1
                logging.info(f"Offre ajoutée : {scraped_data.get('title')}")
            else:
                logging.info("L'offre n'a pas été ajoutée (peut-être un doublon de contenu).")
        else:
            logging.warning(f"Échec du scraping pour l'URL : {url}")
    
    logging.info(f"{new_offers_added_count} nouvelles offres ajoutées à la base de données.")
    return new_offers_added_count

if __name__ == '__main__':
    # Exemple avec des paramètres
    job_params = {
        'job_title': "Développeur Python",
        'skills': ["Django", "Flask", "API REST"],
        'location': "Paris",
        'experience': "2 ans"
    }
    
    # Option 1: Utiliser les paramètres structurés
    added_count_1 = search_and_scrape_jobs(**job_params)
    print(f"Recherche avec paramètres: {added_count_1} nouvelles offres ajoutées.")
    
    # Option 2: Utiliser une requête directe
    query_direct = "offre emploi ingénieur logiciel remote Python"
    added_count_2 = search_and_scrape_jobs(query=query_direct)
    print(f"Recherche directe: {added_count_2} nouvelles offres ajoutées.")