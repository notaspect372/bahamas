import os
import time
import re
import json
from urllib.parse import quote

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# -------------------------------
# Set up headless Chrome options for GitHub Actions
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Initialize the Selenium WebDriver with headless options
driver = webdriver.Chrome(options=chrome_options)

def get_lat_long_from_google_maps(address):
    """
    Fetch latitude and longitude from Google Maps by searching for the address.
    """
    # Encode the address for use in a URL
    search_url = f"https://www.google.com/maps/search/{quote(address)}"
    
    # Initialize default values
    latitude = 'N/A'
    longitude = 'N/A'
    
    try:
        # Navigate to the Google Maps search URL
        driver.get(search_url)
        time.sleep(5)  # Allow time for Google Maps to load
        
        # Get the current URL and extract latitude and longitude using a regex pattern
        current_url = driver.current_url
        url_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', current_url)
        
        if url_match:
            latitude = url_match.group(1)
            longitude = url_match.group(2)
            print(f"Latitude: {latitude}, Longitude: {longitude}")
        else:
            print("Google Maps could not find latitude and longitude. Using default values.")
    except Exception as e:
        print(f"Error occurred while fetching latitude and longitude: {e}")
    
    return latitude, longitude

def scrape_property_details(url):
    """
    Scrape property details from the given property URL.
    """
    driver.get(url)
    time.sleep(3)  # Adjust the delay as needed
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Scrape the property name from meta tag
    name_tag = soup.find('meta', property='og:title')
    name = name_tag['content'] if name_tag else 'N/A'
    
    # Scrape the property address
    address_section = soup.find('span', class_='address')
    address = address_section.text.strip() if address_section else 'N/A'
    
    # Scrape the property price
    price_section = soup.find('span', class_='price-value')
    price = price_section.text.strip() if price_section else 'N/A'
    
    # Scrape characteristics (key-value pairs)
    characteristics = {}
    characteristics_section = soup.find('div', {'id': re.compile(r'info-callout-\d+')})
    if characteristics_section:
        for li in characteristics_section.find_all('li'):
            key_elem = li.find('strong')
            value_elem = li.find('span')
            key = key_elem.text.strip() if key_elem else 'Unknown'
            value = value_elem.text.strip() if value_elem else 'N/A'
            characteristics[key] = value

    # Retrieve the area if available
    area = characteristics.get("Square Feet", "-")
    
    # Scrape the full description
    description_section = soup.find('div', id="info-callout-119816")
    if description_section:
        description_div = description_section.find('div')
        description = description_div.text.strip() if description_div else 'N/A'
    else:
        description = 'N/A'
    
    # Scrape additional features
    features = {}
    features_section = soup.find('div', class_='custom-field-group', id='primary-categories')
    if features_section:
        for li in features_section.find_all('li', class_='field'):
            field_name = li.find('span', class_='field-name')
            field_value = li.find('span', class_='field-value')
            if field_name and field_value:
                key = field_name.get_text(strip=True).replace(':', '')
                value = field_value.get_text(strip=True)
                features[key] = value

    # Get latitude and longitude from Google Maps using the address
    lat, lng = get_lat_long_from_google_maps(address)

    return {
        "URL": url,
        "Name": name,
        "Description": description,
        "Address": address,
        "Area": area,
        "Price": price,
        # Store dictionaries as JSON strings so they can be saved in Excel cells
        "Characteristics": json.dumps(characteristics),
        "Features": json.dumps(features),
        "Latitude": lat,
        "Longitude": lng
    }

# -------------------------------
# Main process

# Ensure the output directory exists for GitHub Actions artifacts
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# 1. Read property URLs from the text file (each URL on a new line)
with open("unique_urls.txt", "r") as file:
    property_urls = [line.strip() for line in file if line.strip()]

# 2. Loop over each URL, scrape property details, and store the results
all_property_details = []
for url in property_urls:
    print(f"Scraping property details for URL: {url}")
    try:
        details = scrape_property_details(url)
        all_property_details.append(details)
    except Exception as e:
        print(f"Error scraping {url}: {e}")

# 3. Create a Pandas DataFrame from the scraped data and save it as an Excel file
df = pd.DataFrame(all_property_details)
excel_file = os.path.join(output_dir, "property_data.xlsx")
df.to_excel(excel_file, index=False)
print(f"Scraped data has been saved to '{excel_file}'.")

# 4. Close the Selenium driver
driver.quit()
