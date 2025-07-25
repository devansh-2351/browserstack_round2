import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json
import re

# Directory to save images
IMAGE_DIR = 'article_images'
os.makedirs(IMAGE_DIR, exist_ok=True)

# Hardcoded API key for translation
RAPIDAPI_KEY = '155f0def90mshb1824db56026878p176a37jsn91d894ced4e3'

def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def run_scraper():
    driver = get_driver()
    results = {}
    try:
        def go_to_opinion_section():
            driver.get('https://elpais.com/')
            time.sleep(3)
            opinion_link = driver.find_element(By.LINK_TEXT, 'Opinión')
            opinion_link.click()
            time.sleep(3)
        def get_first_five_articles():
            # Try to find both featured and regular articles
            articles = []
            seen_links = set()
            # Regex for real opinion articles: /opinion/YYYY-MM-DD/slug.html
            article_pattern = re.compile(r"/opinion/\d{4}-\d{2}-\d{2}/[\w\-]+\.html$")
            # Featured article (often first)
            featured = driver.find_elements(By.CSS_SELECTOR, 'article[data-dtm-region="destacado"] a, article[data-dtm-region="destacado"]')
            for elem in featured:
                try:
                    link = elem.get_attribute('href') or elem.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                    if link and link not in seen_links and article_pattern.search(link):
                        articles.append(link)
                        seen_links.add(link)
                        print(f"DEBUG: Featured article found: {link}")
                        if len(articles) == 5:
                            break
                except Exception as e:
                    print(f"DEBUG: Error extracting featured article link: {e}")
            # Regular articles (grid/list)
            if len(articles) < 5:
                regulars = driver.find_elements(By.CSS_SELECTOR, 'article[data-dtm-region="modulo_1"] a, article[data-dtm-region="modulo_1"]')
                for elem in regulars:
                    try:
                        link = elem.get_attribute('href') or elem.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                        if link and link not in seen_links and article_pattern.search(link):
                            articles.append(link)
                            seen_links.add(link)
                            print(f"DEBUG: Regular article found: {link}")
                            if len(articles) == 5:
                                break
                    except Exception as e:
                        print(f"DEBUG: Error extracting regular article link: {e}")
            # Fallback: any article
            if len(articles) < 5:
                all_articles = driver.find_elements(By.CSS_SELECTOR, 'article a, article')
                for elem in all_articles:
                    try:
                        link = elem.get_attribute('href') or elem.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                        if link and link not in seen_links and article_pattern.search(link):
                            articles.append(link)
                            seen_links.add(link)
                            print(f"DEBUG: Fallback article found: {link}")
                            if len(articles) == 5:
                                break
                    except Exception as e:
                        print(f"DEBUG: Error extracting fallback article link: {e}")
            print(f"DEBUG: Collected {len(articles)} unique article links.")
            return articles[:5]
        def extract_article_info_from_link(link):
            driver.get(link)
            time.sleep(2)
            # Extract title
            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, 'h1, header h1')
                title = title_elem.text.strip()
            except Exception:
                title = 'No title found'
            # Extract cover image
            try:
                img_elem = driver.find_element(By.CSS_SELECTOR, 'img')
                img_url = img_elem.get_attribute('src')
            except Exception:
                img_url = None
            # Extract content
            try:
                paragraphs = driver.find_elements(By.CSS_SELECTOR, 'div[data-dtm-region="articulo_cuerpo"] p')
                if not paragraphs:
                    paragraphs = driver.find_elements(By.CSS_SELECTOR, 'article p')
                content = '\n'.join([p.text for p in paragraphs if p.text.strip()])
            except Exception:
                content = 'No content found.'
            return title, link, img_url, content
        def download_image(img_url, title):
            if not img_url:
                return None
            try:
                response = requests.get(img_url, timeout=10)
                if response.status_code == 200:
                    filename = f"{title[:30].replace(' ', '_').replace('/', '')}.jpg"
                    filepath = os.path.join(IMAGE_DIR, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    return filepath
            except Exception as e:
                print(f"Failed to download image: {e}")
            return None
        go_to_opinion_section()
        article_links = get_first_five_articles()
        if not article_links:
            print("No articles found in the Opinion section.")
        translated_headers = []
        for idx, link in enumerate(article_links, 1):
            title, link, img_url, content = extract_article_info_from_link(link)
            print(f"\nArticle {idx} Title: {title}")
            print(f"Content:\n{content[:500]}...\n")
            img_path = download_image(img_url, title)
            if img_path:
                print(f"Cover image saved to: {img_path}")
            else:
                print("No cover image found.")
            try:
                translated = translate_text(title)
            except Exception as e:
                print(f"Translation failed: {e}")
                translated = title
            print(f"Translated Title: {translated}")
            translated_headers.append(translated)
        repeated = analyze_repeated_words(translated_headers)
        print("\nRepeated words (more than twice) in translated headers:")
        if repeated:
            for word, count in repeated.items():
                print(f"'{word}': {count} times")
        else:
            print("No words repeated more than twice.")
        results['translated_headers'] = translated_headers
        results['repeated'] = repeated
    finally:
        driver.quit()
    return results

def translate_text(text, target_lang='en'):
    url = "https://rapid-translate-multi-traduction.p.rapidapi.com/t"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "rapid-translate-multi-traduction.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    payload = {
        "from": "es",         # Spanish
        "to": target_lang,    # English
        "q": text
    }
    response = requests.post(url, headers=headers, json=payload)
    print("DEBUG API RESPONSE:", response.text)
    return response.text

def analyze_repeated_words(headers):
    from collections import Counter
    import re
    words = []
    for header in headers:
        # Remove punctuation and split
        words += re.findall(r'\b\w+\b', header.lower())
    counter = Counter(words)
    repeated = {word: count for word, count in counter.items() if count > 2}
    return repeated

def main():
    run_scraper()

if __name__ == '__main__':
    main() 