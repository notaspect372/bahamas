import os
import tempfile
import re
import time
from urllib.parse import quote

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service  # Optional: if you need to set a custom chromedriver path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Create output directory if it doesn't exist
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# Create a temporary directory for Chrome user data
chrome_user_data_dir = tempfile.mkdtemp()

# Set up Chrome options for GitHub Actions (headless, etc.)
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run headless in GitHub Actions
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument(f"--user-data-dir={chrome_user_data_dir}")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)

# Optional: specify the chromedriver executable path if needed.
# Example:
# chrome_service = Service("/path/to/chromedriver")
# driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
driver = webdriver.Chrome(options=chrome_options)

# Set up an explicit wait
wait = WebDriverWait(driver, 15)

# List of base URLs to scrape
base_urls = [
    "https://www.bahamasrealty.com/listings/?status=Active,Pending,Active+Under+Contract,Closed,CNT,PCG",
    # Add more URLs here if needed
]

def scrape_property_urls(base_url):
    """Scrape all property URLs from paginated results."""
    page_number = 1
    property_links = []

    while True:
        # Construct the paginated URL
        url = f"{base_url}&page={page_number}"
        print(f"Visiting: {url}")
        driver.get(url)

        # Wait until at least one property listing appears
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.listing__link")))
        except Exception as e:
            print(f"Timeout waiting for listings on page {page_number}: {e}")
        
        # Scroll down to trigger any lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)  # Give time for additional content to load
        
        # Optionally, save the page source for debugging:
        # with open(os.path.join(output_dir, f"page_{page_number}.html"), "w", encoding="utf-8") as f:
        #     f.write(driver.page_source)

        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Extract property URLs on the current page
        page_links = []
        for link in soup.find_all('a', class_='listing__link'):
            href = link.get('href')
            if href:
                full_url = "https://www.bahamasrealty.com" + href
                print(f"Found property URL: {full_url}")
                page_links.append(full_url)

        # If no property URLs were found, break out of the loop
        if not page_links:
            print(f"No property URLs found on page {page_number}, ending pagination.")
            break

        print(f"Total links on page {page_number}: {len(page_links)}")
        property_links.extend(page_links)
        page_number += 1

    return property_links

def get_lat_long_from_google_maps(address):
    """
    Fetch latitude and longitude from Google Maps by searching for the address.
    """
    search_url = f"https://www.google.com/maps/search/{quote(address)}"
    latitude = 'N/A'
    longitude = 'N/A'
    
    try:
        driver.get(search_url)
        # Wait for a short period to allow Google Maps to process the search
        time.sleep(5)
        current_url = driver.current_url
        url_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', current_url)
        if url_match:
            latitude = url_match.group(1)
            longitude = url_match.group(2)
            print(f"Address: {address} -> Latitude: {latitude}, Longitude: {longitude}")
        else:
            print("Could not extract latitude/longitude from URL.")
    except Exception as e:
        print(f"Error during Google Maps lookup for address '{address}': {e}")

    return latitude, longitude

def scrape_property_details(url):
    """Scrape detailed information for a single property URL."""
    driver.get(url)
    
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "meta[property='og:title']")))
    except Exception as e:
        print(f"Timeout waiting for property details on {url}: {e}")
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Get property name
    name_tag = soup.find('meta', property='og:title')
    name = name_tag['content'] if name_tag else 'N/A'

    # Get address
    address_section = soup.find('span', class_='address')
    address = address_section.text.strip() if address_section else 'N/A'

    # Get price
    price_section = soup.find('span', class_='price-value')
    price = price_section.text.strip() if price_section else 'N/A'

    # Get characteristics
    characteristics = {}
    characteristics_section = soup.find('div', {'id': re.compile(r'info-callout-\d+')})
    if characteristics_section:
        for li in characteristics_section.find_all('li'):
            key_tag = li.find('strong')
            value_tag = li.find('span')
            key = key_tag.text.strip() if key_tag else 'Unknown'
            value = value_tag.text.strip() if value_tag else 'N/A'
            characteristics[key] = value

    area = characteristics.get("Square Feet", "-")

    # Get description
    description_section = soup.find('div', id="info-callout-119816")
    if description_section:
        inner_div = description_section.find('div')
        description = inner_div.text.strip() if inner_div else 'N/A'
    else:
        description = 'N/A'

    # Get features
    features = {}
    features_section = soup.find('div', class_='custom-field-group', id='primary-categories')
    if features_section:
        for li in features_section.find_all('li', class_='field'):
            key = li.find('span', class_='field-name').get_text(strip=True).replace(':', '')
            value = li.find('span', class_='field-value').get_text(strip=True)
            features[key] = value

    # Get latitude and longitude from Google Maps
    lat, long = get_lat_long_from_google_maps(address)

    property_data = {
        "URL": url,
        "Name": name,
        "Description": description,
        "Address": address,
        "Area": area,
        "Price": price,
        "Characteristics": characteristics,
        "Features": features,
        "Latitude": lat,
        "Longitude": long
    }

    print(f"Scraped data for property: {property_data}")
    return property_data

# Main process
all_data = []
for base_url in base_urls:
    print(f"Scraping base URL: {base_url}")
    property_urls = scrape_property_urls(base_url)
    print(f"Total property URLs found: {len(property_urls)}")

    for property_url in property_urls:
        data = scrape_property_details(property_url)
        all_data.append(data)

    # Save data for this base URL to an Excel file
    df = pd.DataFrame(all_data)
    safe_base = re.sub(r'[\\/*?:"<>|]', "", f"{base_url.replace('/', '_').replace(':', '')}")
    file_name = os.path.join(output_dir, f"{safe_base}.xlsx")
    df.to_excel(file_name, index=False)
    print(f"Saved data for {base_url} to {file_name}")

# Clean up and close the driver
driver.quit()
