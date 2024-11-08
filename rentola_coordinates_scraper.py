import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
import re
from math import radians, sin, cos, sqrt, atan2

class RentolaCoordinatesScraper:
    def __init__(self, max_apartments=200):
        # Your workplace coordinates
        self.workplace_lat = 47.5447459
        self.workplace_lng = 19.0728113
        self.max_distance = 3  # kilometers
        self.max_apartments = max_apartments  # Maximum number of apartments to check
        
        self.base_url = "https://rentola.com/for-rent"
        self.search_params = {
            "location": "budapest",
            "rent_per": "month",
            "rent": "0-700",#price
            "rooms": "2-3"#rooms
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        self.listings_pattern = re.compile(r'https://rentola\.com/listings/[^/]+$')

    def calculate_distance(self, lat2, lon2):
        R = 6371  # Earth's radius in kilometers
        lat1 = radians(self.workplace_lat)
        lon1 = radians(self.workplace_lng)
        lat2 = radians(float(lat2))
        lon2 = radians(float(lon2))
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance

    def build_url(self, page=1):
        params = []
        for key, value in self.search_params.items():
            params.append(f"{key}={value}")
        query_string = '&'.join(params)
        if page > 1:
            query_string += f"&page={page}"
        url = f"{self.base_url}?{query_string}"
        return url

    def is_valid_listing_url(self, url):
        if not url.startswith('http'):
            url = f"https://rentola.com{url}"
        return bool(self.listings_pattern.match(url))

    def get_coordinates_and_price(self, url):
        try:
            print(f"Fetching details for: {url}")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            map_div = soup.find('div', class_='leaflet-map')
            if map_div:
                lat = map_div.get('data-lat')
                lng = map_div.get('data-lng')
                
                price_elem = soup.find('div', class_='price') or soup.find('span', class_='price')
                price = price_elem.text.strip() if price_elem else "Price not listed"
                
                if lat and lng:
                    return float(lat), float(lng), price
            return None, None, None
        except Exception as e:
            print(f"Error getting details for {url}: {e}")
            return None, None, None

    def scrape_listings(self):
        page = 1
        listings_data = []
        seen_urls = set()
        total_checked = 0
        within_range = 0

        while total_checked < self.max_apartments:
            url = self.build_url(page)
            print(f"\nFetching page {page}...")
            print(f"Total apartments checked: {total_checked}/{self.max_apartments}")
            
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                links_found = 0
                
                for a in soup.find_all('a', href=True):
                    if total_checked >= self.max_apartments:
                        print(f"\nReached maximum number of apartments to check ({self.max_apartments})")
                        break
                        
                    href = a['href']
                    full_url = f"https://rentola.com{href}" if not href.startswith('http') else href
                    
                    if self.is_valid_listing_url(full_url) and full_url not in seen_urls:
                        seen_urls.add(full_url)
                        links_found += 1
                        total_checked += 1
                        
                        print(f"\nChecking apartment {total_checked}/{self.max_apartments}")
                        lat, lng, price = self.get_coordinates_and_price(full_url)
                        if lat and lng:
                            distance = self.calculate_distance(lat, lng)
                            
                            if distance <= self.max_distance:
                                within_range += 1
                                listings_data.append({
                                    'url': full_url,
                                    'latitude': lat,
                                    'longitude': lng,
                                    'distance': round(distance, 2),
                                    'price': price
                                })
                                print(f"✓ Within range! Distance: {distance:.2f} km, Price: {price}")
                            else:
                                print(f"✗ Too far: {distance:.2f} km")
                        
                        time.sleep(1)
                
                print(f"\nPage {page} summary:")
                print(f"Found {links_found} new listings")
                print(f"Total checked: {total_checked}")
                print(f"Total within {self.max_distance}km: {within_range}")
                
                if links_found == 0:
                    print("No new listings found on this page, stopping...")
                    break
                
                page += 1
                time.sleep(2)
                
            except Exception as e:
                print(f"Error on page {page}: {str(e)}")
                break
        
        return listings_data

    def save_results(self, listings):
        # Sort listings by distance
        listings.sort(key=lambda x: x['distance'])
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON format
        json_filename = f"rentola_listings_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'total_checked': self.max_apartments,
                    'max_distance': self.max_distance,
                    'workplace_coordinates': {
                        'latitude': self.workplace_lat,
                        'longitude': self.workplace_lng
                    }
                },
                'listings': listings
            }, f, indent=2, ensure_ascii=False)
        
        # Save text format
        txt_filename = f"rentola_listings_{timestamp}.txt"
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(f"Listings within {self.max_distance}km of workplace\n")
            f.write(f"Checked {self.max_apartments} apartments in total\n")
            f.write(f"Found {len(listings)} apartments within range\n")
            f.write(f"Workplace coordinates: {self.workplace_lat}, {self.workplace_lng}\n")
            f.write("=" * 50 + "\n\n")
            
            for listing in listings:
                f.write(f"Distance: {listing['distance']} km\n")
                f.write(f"Price: {listing['price']}\n")
                f.write(f"URL: {listing['url']}\n")
                f.write(f"Coordinates: {listing['latitude']}, {listing['longitude']}\n")
                f.write("-" * 50 + "\n")
        
        return json_filename, txt_filename

def main():
    MAX_APARTMENTS = 200  # Limit to 200 apartments
    
    print("Starting Rentola coordinates scraper...")
    print(f"Will check maximum {MAX_APARTMENTS} apartments")
    print("Filtering for locations within 3km of workplace")
    print(f"Workplace coordinates: 47.5447459, 19.0728113")
    
    scraper = RentolaCoordinatesScraper(max_apartments=MAX_APARTMENTS)
    listings = scraper.scrape_listings()
    
    # Save results
    json_file, txt_file = scraper.save_results(listings)
    
    # Print summary
    print(f"\nScraping completed!")
    print(f"Checked {MAX_APARTMENTS} apartments in total")
    print(f"Found {len(listings)} listings within 3km")
    print(f"Results saved to:")
    print(f"- JSON: {json_file}")
    print(f"- Text: {txt_file}")

if __name__ == "__main__":
    main()