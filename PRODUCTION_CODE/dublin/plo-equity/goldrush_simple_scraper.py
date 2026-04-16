#!/usr/bin/env python3
"""
GoldRush PLO Table Scraper - Simple HTML Parser
Fetches GoldRush live poker page and extracts PLO table data.
"""

import re
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup

OUTPUT_JSON = "/opt/plo-equity/goldrush_tables.json"

def scrape_goldrush():
    """Fetch and parse GoldRush tables."""
    print("Fetching GoldRush live poker page...")
    
    try:
        url = "https://www.goldrush.co.za/live-poker"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        print(f"Got response: {len(response.text)} bytes")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for table data in the HTML
        tables = []
        text_content = soup.get_text()
        
        # Search for PLO patterns in the text
        plo4_matches = re.findall(r'(PLO4|Omaha.*4|4.*Card.*Omaha)', text_content, re.I)
        plo6_matches = re.findall(r'(PLO6|Omaha.*6|6.*Card.*Omaha)', text_content, re.I)
        
        print(f"Found {len(plo4_matches)} PLO4 mentions, {len(plo6_matches)} PLO6 mentions")
        
        # Try to find structured table data
        for elem in soup.find_all(['tr', 'div', 'li', 'td']):
            text = elem.get_text(' ', strip=True)
            
            # Check if this element mentions PLO
            if re.search(r'PLO|Omaha', text, re.I):
                # Try to extract table info
                name_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
                stakes_match = re.search(r'(?:R|ZAR)\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)', text, re.I)
                
                isPLO6 = bool(re.search(r'PLO6|Omaha.*6|6.*Card', text, re.I))
                isPLO4 = bool(re.search(r'PLO4|Omaha.*4|4.*Card', text, re.I))
                
                if (isPLO4 or isPLO6) and stakes_match:
                    table = {
                        'name': name_match.group(1) if name_match else 'Unknown',
                        'game_type': 'PLO6' if isPLO6 else 'PLO4',
                        'small_blind': float(stakes_match.group(1)),
                        'big_blind': float(stakes_match.group(2)),
                        'stakes_display': f"R {stakes_match.group(1)}/{stakes_match.group(2)}",
                        'seats_total': 6,
                        'platform': 'GoldRush'
                    }
                    tables.append(table)
        
        # Deduplicate
        unique_tables = []
        seen = set()
        for t in tables:
            key = f"{t['name']}_{t['stakes_display']}"
            if key not in seen:
                seen.add(key)
                unique_tables.append(t)
        
        # Save to JSON
        data = {
            'platform': 'GoldRush',
            'scraped_at': datetime.utcnow().isoformat(),
            'count': len(unique_tables),
            'tables': unique_tables
        }
        
        with open(OUTPUT_JSON, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Saved {len(unique_tables)} unique tables to {OUTPUT_JSON}")
        
        return {
            'ok': True,
            'count': len(unique_tables),
            'tables': unique_tables
        }
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return {
            'ok': False,
            'error': str(e),
            'tables': []
        }

if __name__ == '__main__':
    result = scrape_goldrush()
    print(json.dumps(result, indent=2))
