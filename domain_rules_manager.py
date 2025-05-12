import json
import os
import logging
from urllib.parse import urlparse
import re
from bs4 import BeautifulSoup
import requests
import random
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Fichier pour stocker les règles de scraping par domaine
RULES_FILE = "domain_rules.json"

def get_domain(url):
    """Extrait le domaine principal d'une URL"""
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        # Obtenir le domaine principal (ex: example.com à partir de subdomain.example.com)
        parts = domain.split('.')
        if len(parts) > 2:
            domain = '.'.join(parts[-2:])
        return domain
    except Exception as e:
        logging.error(f"Erreur lors de l'extraction du domaine: {e}")
        return None

def load_domain_rules():
    """Charge les règles de scraping depuis le fichier JSON"""
    if not os.path.exists(RULES_FILE):
        return {}
    
    try:
        with open(RULES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erreur lors du chargement des règles: {e}")
        return {}

def save_domain_rules(rules):
    """Sauvegarde les règles de scraping dans le fichier JSON"""
    try:
        with open(RULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=4, ensure_ascii=False)
        logging.info(f"Règles sauvegardées dans {RULES_FILE}")
    except Exception as e:
        logging.error(f"Erreur lors de la sauvegarde des règles: {e}")

def find_candidate_selectors(soup, element_text, tag_types, max_candidates=3):
    """
    Trouve des sélecteurs CSS potentiels pour un élément basé sur son texte.
    
    Args:
        soup: Objet BeautifulSoup de la page
        element_text: Texte contenu dans l'élément à trouver
        tag_types: Liste de types de balises à rechercher (ex: ['h1', 'div', 'span'])
        max_candidates: Nombre maximum de sélecteurs à retourner
        
    Returns:
        Liste de sélecteurs CSS potentiels
    """
    if not element_text or not soup or not tag_types:
        return []
    
    # Nettoyer le texte pour la recherche
    clean_text = re.sub(r'\s+', ' ', element_text).strip()
    if len(clean_text) < 10:  # Ignorer les textes trop courts
        return []
    
    candidates = []
    
    # Chercher des éléments contenant le texte exact ou une partie
    for tag in tag_types:
        elements = soup.find_all(tag)
        for element in elements:
            element_text = element.get_text(strip=True)
            if clean_text in element_text or element_text in clean_text:
                # Créer un sélecteur CSS basé sur les classes et l'ID
                selector = tag
                
                # Ajouter l'ID s'il existe
                if element.get('id'):
                    selector += f"#{element['id']}"
                # Sinon, ajouter les classes s'il y en a
                elif element.get('class'):
                    classes = '.'.join(element['class'])
                    selector += f".{classes}"
                
                # Si on a déjà un sélecteur avec ID ou classe, l'ajouter
                if selector != tag:
                    candidates.append(selector)
                
                # Essayer de créer un sélecteur avec le chemin partiel
                parent = element.parent
                if parent and parent.name != 'body':
                    parent_selector = parent.name
                    if parent.get('class'):
                        parent_classes = '.'.join(parent['class'])
                        parent_selector += f".{parent_classes}"
                    
                    selector_with_parent = f"{parent_selector} > {selector}"
                    candidates.append(selector_with_parent)
    
    # Enlever les doublons et limiter le nombre
    unique_candidates = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
            if len(unique_candidates) >= max_candidates:
                break
    
    return unique_candidates

def fetch_html(url):
    """Récupère le HTML d'une page web"""
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    ]
    
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logging.error(f"Erreur lors de la récupération de {url}: {e}")
        return None

def learn_from_successful_scrape(url, title, description, company=None, location=None):
    """
    Analyse une page d'offre d'emploi scrapée avec succès pour apprendre
    les sélecteurs à utiliser pour ce domaine à l'avenir.
    """
    domain = get_domain(url)
    if not domain:
        return False
    
    # Charger les règles existantes
    domain_rules = load_domain_rules()
    
    # Vérifier si on a déjà des règles pour ce domaine
    if domain in domain_rules:
        logging.info(f"Des règles existent déjà pour {domain}, pas d'apprentissage nécessaire.")
        return False
    
    # Récupérer le HTML de la page
    html_content = fetch_html(url)
    if not html_content:
        return False
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Créer des règles pour ce domaine
    new_rules = {}
    
    # Trouver des sélecteurs pour le titre
    if title and title != "Titre non trouvé":
        title_selectors = find_candidate_selectors(soup, title, ['h1', 'h2', 'div', 'span'], max_candidates=3)
        if title_selectors:
            new_rules['title'] = title_selectors
    
    # Trouver des sélecteurs pour la description
    if description and description != "Description non trouvée" and len(description) > 100:
        # Pour la description, chercher des conteneurs plus larges
        desc_selectors = find_candidate_selectors(soup, description[:200], ['div', 'article', 'section', 'main'], max_candidates=3)
        if desc_selectors:
            new_rules['description'] = desc_selectors
    
    # Trouver des sélecteurs pour l'entreprise
    if company and company != "Entreprise non trouvée":
        company_selectors = find_candidate_selectors(soup, company, ['div', 'span', 'p', 'a'], max_candidates=3)
        if company_selectors:
            new_rules['company'] = company_selectors
    
    # Trouver des sélecteurs pour la localisation
    if location and location != "Localisation non trouvée":
        location_selectors = find_candidate_selectors(soup, location, ['div', 'span', 'p', 'li'], max_candidates=3)
        if location_selectors:
            new_rules['location'] = location_selectors
    
    # Si on a trouvé des règles, les ajouter et sauvegarder
    if new_rules:
        domain_rules[domain] = new_rules
        save_domain_rules(domain_rules)
        logging.info(f"Nouvelles règles apprises pour le domaine {domain}: {new_rules}")
        return True
    else:
        logging.warning(f"Impossible d'apprendre des règles pour {domain}")
        return False

def test_domain_rules(url, rules):
    """
    Teste les règles de scraping sur une URL spécifique
    et retourne les résultats pour chaque champ.
    """
    html_content = fetch_html(url)
    if not html_content:
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    results = {}
    
    for field, selectors in rules.items():
        results[field] = []
        
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    results[field].append({
                        'selector': selector,
                        'text': text[:100] + ('...' if len(text) > 100 else '')
                    })
            except Exception as e:
                logging.error(f"Erreur avec le sélecteur {selector}: {e}")
    
    return results

def suggest_domain_rules_improvements(domain):
    """
    Suggère des améliorations pour les règles d'un domaine spécifique
    en utilisant des URL récemment scrapées.
    """
    # Cette fonction pourrait utiliser des techniques plus avancées
    # comme comparer plusieurs pages d'offres du même site pour
    # identifier des patterns communs
    pass

def import_rules_from_scraper_utils():
    """
    Importe les règles définies dans scraper_utils.py
    et les ajoute au fichier de règles JSON.
    """
    try:
        from scraper_utils import DOMAIN_RULES
        
        # Charger les règles existantes
        current_rules = load_domain_rules()
        
        # Ajouter/mettre à jour avec les règles de scraper_utils
        for domain, rules in DOMAIN_RULES.items():
            if domain not in current_rules:
                current_rules[domain] = rules
            else:
                # Fusionner les règles existantes avec les nouvelles
                for field, selectors in rules.items():
                    if field not in current_rules[domain]:
                        current_rules[domain][field] = selectors
                    else:
                        # Ajouter les nouveaux sélecteurs s'ils n'existent pas déjà
                        for selector in selectors:
                            if selector not in current_rules[domain][field]:
                                current_rules[domain][field].append(selector)
        
        # Sauvegarder les règles mises à jour
        save_domain_rules(current_rules)
        logging.info(f"Règles importées depuis scraper_utils.py")
        return True
    except Exception as e:
        logging.error(f"Erreur lors de l'importation des règles: {e}")
        return False

def export_rules_to_scraper_utils():
    """
    Exporte les règles du fichier JSON vers un format
    utilisable dans scraper_utils.py.
    """
    rules = load_domain_rules()
    if not rules:
        logging.warning("Aucune règle à exporter")
        return None
    
    python_code = "DOMAIN_RULES = {\n"
    
    for domain, domain_rules in rules.items():
        python_code += f"    '{domain}': {{\n"
        
        for field, selectors in domain_rules.items():
            selector_str = ", ".join([f"'{s}'" for s in selectors])
            python_code += f"        '{field}': [{selector_str}],\n"
        
        python_code += "    },\n"
    
    python_code += "}"
    
    return python_code

if __name__ == '__main__':
    # Exemples d'utilisation
    
    # 1. Importer les règles existantes depuis scraper_utils.py
    import_rules_from_scraper_utils()
    
    # 2. Apprendre de nouvelles règles à partir d'un scraping réussi
    test_url = "https://www.welcometothejungle.com/fr/companies/artefact/jobs/data-scientist_paris"
    learn_from_successful_scrape(
        url=test_url,
        title="Data Scientist",
        description="Nous recherchons un Data Scientist talentueux pour rejoindre notre équipe...",
        company="Artefact",
        location="Paris"
    )
    
    # 3. Exporter les règles pour les utiliser dans scraper_utils.py
    print(export_rules_to_scraper_utils())