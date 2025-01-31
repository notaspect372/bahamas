import os
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import pandas as pd
import re
import json
from urllib.parse import quote

# Create output directory if it doesn't exist
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# Create a temporary directory for Chrome user data
chrome_user_data_dir = tempfile.mkdtemp()

# Set up Chrome options for GitHub Actions (headless, etc.)
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run headless in GitHub Actions
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument(f"--user-data-dir={chrome_user_data_dir}")

# Optionally, if your ChromeDriver is in a specific location, specify the executable path.
# For example:
# chrome_service = Service("/path/to/chromedriver")
# driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

# Otherwise, if chromedriver is in PATH:
driver = webdriver.Chrome(options=chrome_options)

# List of base URLs to scrape
base_urls = [
    "https://www.bahamasrealty.com/listings/?status=Active,Pending,Active+Under+Contract,Closed,CNT,PCG",
    # Add more URLs here
]

# Function to scrape property URLs for a single base URL
def scrape_property_urls(base_url):
    page_number = 1
    property_links = []

    while True:
        # Construct the paginated URL
        url = f"{base_url}&page={page_number}"
        print(f"Visiting: {url}")
        driver.get(url)
        
        # Wait for the page to load fully
        time.sleep(5)
        
        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract property URLs on the current page
        page_links = []
        for link in soup.find_all('a', class_='listing__link'):
            href = link.get('href')
            if href:
                full_url = "https://www.bahamasrealty.com" + href
                print(full_url)
                page_links.append(full_url)

        # Break the loop if no new property URLs are found
        if not page_links:
            break
        
        # Append the current page's property links to the main list
        print(f"Total links on page {page_number}: {len(page_links)}")
        property_links.extend(page_links)
        
        # Increment the page number for the next iteration
        page_number += 1

    return property_links

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
            print("Google Maps could not find latitude and longitude. Falling back to default values.")   
    except Exception as e:
        print(f"Error occurred while fetching latitude and longitude: {e}")
    
    return latitude, longitude

# Function to scrape property details from a property URL
def scrape_property_details(url):
    driver.get(url)
    time.sleep(3)  # Adjust the delay as needed
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Scrape details with error handling
    name = soup.find('meta', property='og:title')
    name = name['content'] if name else 'N/A'
    
    address_section = soup.find('span', class_='address')
    address = address_section.text.strip() if address_section else 'N/A'
    
    price_section = soup.find('span', class_='price-value')
    price = price_section.text.strip() if price_section else 'N/A'
    
    # Characteristics (store in key-value pairs)
    characteristics = {}
    characteristics_section = soup.find('div', {'id': re.compile(r'info-callout-\d+')})
    if characteristics_section:
        for li in characteristics_section.find_all('li'):
            key = li.find('strong').text.strip() if li.find('strong') else 'Unknown'
            value = li.find('span').text.strip() if li.find('span') else 'N/A'
            characteristics[key] = value

    area = characteristics.get("Square Feet", "-")

    # Description
    description_section = soup.find('div', id="info-callout-119816")
    if description_section:
        description = description_section.find('div').text.strip()
    else:
        description = 'N/A'

    features = {}
    features_section = soup.find('div', class_='custom-field-group', id='primary-categories')
    if features_section:
        for li in features_section.find_all('li', class_='field'):
            key = li.find('span', class_='field-name').get_text(strip=True).replace(':', '')
            value = li.find('span', class_='field-value').get_text(strip=True)
            features[key] = value

    lat, long = get_lat_long_from_google_maps(address)

    return {
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

# Main process
for base_url in base_urls:
    all_property_links = scrape_property_urls(base_url)
    print(f"Total property URLs found: {len(all_property_links)}")
    all_data = []
    
    # Scrape details for each property URL
    for property_url in all_property_links:
        data = scrape_property_details(property_url)
        print(data)
        all_data.append(data)
    
    # Convert data to DataFrame and save to Excel inside the output directory
    df = pd.DataFrame(all_data)
    # Clean the base URL for the file name by replacing problematic characters
    safe_base = re.sub(r'[\\/*?:"<>|]', "", f"{base_url.replace('/', '_').replace(':', '')}")
    file_name = os.path.join(output_dir, f"{safe_base}.xlsx")
    df.to_excel(file_name, index=False)
    print(f"Saved data for {base_url} to {file_name}")

# Close the driver after scraping
driver.quit()
