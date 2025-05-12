import requests
from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import urlparse
import time
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Liste de User-Agents variés pour éviter d'être bloqué
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

# Dictionnaire de règles de scraping par domaine
# Format: {
#   'domain.com': {
#       'title': [liste de sélecteurs CSS ou XPath pour le titre],
#       'description': [liste de sélecteurs pour la description],
#       'company': [liste de sélecteurs pour l'entreprise],
#       'location': [liste de sélecteurs pour la localisation]
#   }
# }
DOMAIN_RULES = {
    'welcometothejungle.com': {
        'title': ['h1.sc-1uownj7-0', 'h1.ais7m6-0', 'h1'],
        'description': ['div.sc-2j2v96-0', 'div[data-testid="job-description"]', 'div.jd-container'],
        'company': ['div.sc-bqWxrE', 'div.sc-1h0mp4p-0', 'a.sc-18bqcmu-1'],
        'location': ['div.sc-168vpsi-0', 'span[data-testid="job-location"]']
    },
    'apec.fr': {
        'title': ['h1.title', 'h1.offer-title', 'div.offer-title h1'],
        'description': ['div.container-justify-text', 'div.details-offer-body', 'div.details-offer'],
        'company': ['p.org-name', 'div.org-name'],
        'location': ['li.location span', 'p.location']
    },
    # Ajoutez d'autres sites selon vos besoins
}

# Expressions régulières pour identifier des sections communes
# Ces patterns peuvent aider à extraire des informations même sans règles spécifiques au domaine
COMMON_PATTERNS = {
    'company': [
        r'société\s*:?\s*([\w\s\-\'\.&]+)',
        r'entreprise\s*:?\s*([\w\s\-\'\.&]+)',
        r'company\s*:?\s*([\w\s\-\'\.&]+)'
    ],
    'location': [
        r'lieu\s*:?\s*([\w\s\-\'\.&,]+)',
        r'localisation\s*:?\s*([\w\s\-\'\.&,]+)',
        r'location\s*:?\s*([\w\s\-\'\.&,]+)'
    ]
}

def get_element_text(soup, selectors):
    """Tente d'extraire le texte en utilisant une liste de sélecteurs"""
    for selector in selectors:
        try:
            if selector.startswith('//'):  # XPath
                import lxml.html
                dom = lxml.html.fromstring(str(soup))
                elements = dom.xpath(selector)
                if elements:
                    return ' '.join(el.text_content().strip() for el in elements if el.text_content().strip())
            else:  # CSS
                element = soup.select_one(selector)
                if element:
                    return element.get_text(strip=True)
        except Exception as e:
            logging.info(f"Erreur avec le sélecteur {selector}: {e}")
    return None

def extract_with_patterns(text, patterns):
    """Tente d'extraire des informations en utilisant des expressions régulières"""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def find_longest_text_block(soup, min_length=100, excluded_tags=None):
    """Trouve le bloc de texte le plus long dans la page"""
    if excluded_tags is None:
        excluded_tags = ['script', 'style', 'header', 'footer', 'nav']
    
    # Exclure certaines balises
    for tag in excluded_tags:
        for element in soup.find_all(tag):
            element.decompose()
    
    # Trouver tous les éléments de texte
    text_elements = []
    for tag in ['div', 'article', 'section', 'main']:
        for element in soup.find_all(tag):
            text = element.get_text(strip=True)
            if len(text) >= min_length:
                text_elements.append((element, len(text)))
    
    # Trier par longueur de texte
    text_elements.sort(key=lambda x: x[1], reverse=True)
    
    if text_elements:
        return text_elements[0][0].get_text(separator='\n', strip=True)
    return None

def clean_text(text):
    """Nettoie le texte en supprimant les espaces multiples, etc."""
    if not text:
        return ""
    # Remplacer les retours à la ligne multiples par un seul
    text = re.sub(r'\n+', '\n', text)
    # Remplacer les espaces multiples par un seul
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_domain(url):
    """Extrait le domaine principal d'une URL"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    # Obtenir le domaine principal (ex: example.com à partir de subdomain.example.com)
    parts = domain.split('.')
    if len(parts) > 2:
        domain = '.'.join(parts[-2:])
    return domain

def extract_job_details(soup, url):
    """Extrait les détails de l'offre d'emploi en fonction du domaine ou de façon générique"""
    domain = get_domain(url)
    result = {
        "title": None,
        "description_full": None,
        "company": None,
        "location": None
    }
    
    # Utiliser des règles spécifiques au domaine si disponibles
    rules = DOMAIN_RULES.get(domain)
    
    # 1. D'abord essayer d'extraire avec les règles spécifiques au domaine
    if rules:
        for field, selectors in rules.items():
            result[field] = get_element_text(soup, selectors)
    
    # 2. Pour les champs toujours manquants, utiliser des méthodes génériques
    
    # Pour le titre (si non trouvé)
    if not result["title"]:
        # Essayer h1, puis titre de la page
        h1 = soup.find('h1')
        if h1:
            result["title"] = h1.get_text(strip=True)
        else:
            title_tag = soup.find('title')
            if title_tag:
                result["title"] = title_tag.get_text(strip=True)
    
    # Pour la description (si non trouvée)
    if not result["description_full"]:
        # 1. Essayer de trouver un conteneur principal de contenu
        for selector in ['main', 'article', '[role="main"]', '#main-content', '.job-description']:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 200:
                result["description_full"] = content.get_text(separator='\n', strip=True)
                break
        
        # 2. Si rien n'est trouvé, chercher le plus grand bloc de texte
        if not result["description_full"]:
            result["description_full"] = find_longest_text_block(soup)
    
    # 3. Pour l'entreprise et la localisation, utiliser des patterns si non trouvés
    page_text = soup.get_text()
    
    if not result["company"]:
        result["company"] = extract_with_patterns(page_text, COMMON_PATTERNS['company'])
    
    if not result["location"]:
        result["location"] = extract_with_patterns(page_text, COMMON_PATTERNS['location'])
    
    # Nettoyer et formater les résultats
    for field in result:
        if result[field]:
            result[field] = clean_text(result[field])
    
    # Limiter la longueur du titre et de la description
    if result["title"] and len(result["title"]) > 150:
        result["title"] = result["title"][:147] + "..."
    
    if result["description_full"] and len(result["description_full"]) > 5000:
        result["description_full"] = result["description_full"][:4997] + "..."
    
    return result

def scrape_job_page(url: str) -> dict:
    """
    Scrape une page d'offre d'emploi donnée avec une approche plus robuste.
    """
    # Sélectionner un User-Agent aléatoire
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        # Délai aléatoire pour éviter la détection
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Vérifier que c'est bien du HTML
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
            logging.warning(f"Le contenu n'est pas HTML: {content_type}")
            return {
                "url": url,
                "title": "Format non supporté",
                "description_full": "Le contenu n'est pas au format HTML",
                "company": "N/A",
                "location": "N/A"
            }
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extraire les détails du job
        job_details = extract_job_details(soup, url)
        
        # Vérifier si on a au moins un titre et une description
        if not job_details["title"] or not job_details["description_full"]:
            logging.warning(f"Impossible d'extraire les informations essentielles pour {url}")
            if not job_details["title"]:
                job_details["title"] = "Titre non trouvé"
            if not job_details["description_full"]:
                job_details["description_full"] = "Description non trouvée"
        
        # Ajouter l'URL au résultat
        result = {
            "url": url,
            "title": job_details["title"] or "Titre non trouvé",
            "description_full": job_details["description_full"] or "Description non trouvée",
            "company": job_details["company"] or "Entreprise non trouvée",
            "location": job_details["location"] or "Localisation non trouvée"
        }
        
        logging.info(f"Scraping réussi pour : {url}")
        return result

    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur de requête pour {url}: {e}")
    except Exception as e:
        logging.error(f"Erreur de scraping pour {url}: {e}")
    
    return {
        "url": url,
        "title": "Erreur de scraping",
        "description_full": "Erreur de scraping",
        "company": "N/A",
        "location": "N/A"
    }

def add_domain_rules(domain, title_selectors=None, description_selectors=None, 
                     company_selectors=None, location_selectors=None):
    """
    Ajoute ou met à jour les règles de scraping pour un domaine spécifique.
    Utile pour étendre les règles sans modifier le code source.
    """
    if domain not in DOMAIN_RULES:
        DOMAIN_RULES[domain] = {}
    
    if title_selectors:
        DOMAIN_RULES[domain]['title'] = title_selectors
    if description_selectors:
        DOMAIN_RULES[domain]['description'] = description_selectors
    if company_selectors:
        DOMAIN_RULES[domain]['company'] = company_selectors
    if location_selectors:
        DOMAIN_RULES[domain]['location'] = location_selectors
    
    logging.info(f"Règles ajoutées pour le domaine: {domain}")

if __name__ == '__main__':
    # Exemple d'ajout de règles pour un nouveau domaine
    add_domain_rules(
        'exemple-job-site.com',
        title_selectors=['h1.job-title', '.offer-header h1'],
        description_selectors=['.job-description', 'div.description-content'],
        company_selectors=['.company-name', 'span.employer'],
        location_selectors=['.job-location', 'div.location span']
    )
    
    # Exemple de test (remplacez par une vraie URL d'offre d'emploi pour tester)
    test_url = "https://www.welcometothejungle.com/fr/companies/artefact/jobs/data-scientist_paris"
    # test_url = "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/169006011W"
    
    if test_url:
        print(f"Test du scraping sur: {test_url}")
        data = scrape_job_page(test_url)
        print(f"Titre: {data.get('title')}")
        print(f"Entreprise: {data.get('company')}")
        print(f"Localisation: {data.get('location')}")
        print(f"Description (début): {data.get('description_full', '')[:500]}...")
    else:
        print("Veuillez fournir une URL de test valide.")