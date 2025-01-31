from selenium import webdriver
from bs4 import BeautifulSoup
import time
import pandas as pd
import re
import os
from urllib.parse import quote

# Ensure the output directory exists
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# Set up the Selenium WebDriver (headless mode for GitHub Actions)
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)

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
        url = f"{base_url}&page={page_number}"
        print(f"Visiting: {url}")
        driver.get(url)
        time.sleep(5)  # Adjust the delay as needed

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Extract property URLs on the current page
        page_links = []
        for link in soup.find_all('a', class_='listing__link'):
            href = link.get('href')
            if href:
                full_url = "https://www.bahamasrealty.com" + href
                print(full_url)
                page_links.append(full_url)

        if not page_links:
            break  # Stop if no more property links found

        property_links.extend(page_links)
        page_number += 1

    return property_links

# Function to get latitude and longitude from Google Maps
def get_lat_long_from_google_maps(address):
    search_url = f"https://www.google.com/maps/search/{quote(address)}"
    latitude, longitude = 'N/A', 'N/A'

    try:
        driver.get(search_url)
        time.sleep(5)
        current_url = driver.current_url
        url_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', current_url)

        if url_match:
            latitude, longitude = url_match.group(1), url_match.group(2)
            print(f"Latitude: {latitude}, Longitude: {longitude}")
        else:
            print("Google Maps could not find latitude and longitude.")
    except Exception as e:
        print(f"Error fetching latitude and longitude: {e}")

    return latitude, longitude

# Function to scrape property details from a property URL
def scrape_property_details(url):
    driver.get(url)
    time.sleep(3)  # Adjust as needed
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Scrape property details
    name = soup.find('meta', property='og:title')
    name = name['content'] if name else 'N/A'

    address_section = soup.find('span', class_='address')
    address = address_section.text.strip() if address_section else 'N/A'

    price_section = soup.find('span', class_='price-value')
    price = price_section.text.strip() if price_section else 'N/A'

    # Scrape characteristics
    characteristics = {}
    characteristics_section = soup.find('div', {'id': re.compile(r'info-callout-\d+')})
    if characteristics_section:
        for li in characteristics_section.find_all('li'):
            key = li.find('strong').text.strip() if li.find('strong') else 'Unknown'
            value = li.find('span').text.strip() if li.find('span') else 'N/A'
            characteristics[key] = value

    area = characteristics.get("Square Feet", "-")

    # Scrape description
    description_section = soup.find('div', id="info-callout-119816")
    description = description_section.find('div').text.strip() if description_section else 'N/A'

    # Scrape features
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
    print(f"length of property urls: {all_property_links}")
    all_data = []

    for property_url in all_property_links:
        data = scrape_property_details(property_url)
        print(data)
        all_data.append(data)

    # Convert data to DataFrame and save to Excel
    df = pd.DataFrame(all_data)
    file_name = re.sub(r'[\\/*?:"<>|]', "", f"{base_url.replace('/', '_').replace(':', '')}.xlsx")
    output_path = os.path.join(output_dir, file_name)
    df.to_excel(output_path, index=False)
    print(f"Saved data to {output_path}")

# Close the driver
driver.quit()
