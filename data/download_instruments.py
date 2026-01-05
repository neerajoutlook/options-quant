#!/usr/bin/env python3
"""
Download and cache Shoonya instruments master file
Run this once per day to get latest symbols and tokens
"""
import sys
sys.path.insert(0, '/Users/neerajsharma/personal/python-projects/options-quant')

from core.shoonya_client import ShoonyaSession
import json
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

def download_instruments():
    """Download instruments master from Shoonya API"""
    session = ShoonyaSession()
    session.login()
    
    logger.info("Downloading instruments from Shoonya...")
    
    # Download for multiple exchanges
    exchanges = ["NSE", "NFO", "BSE", "BFO"]
    
    for exchange in exchanges:
        logger.info(f"Fetching {exchange} instruments...")
        
        # Shoonya provides a file download endpoint
        # Format: https://api.shoonya.com/NSE_symbols.txt.zip
        url = f"https://api.shoonya.com/{exchange}_symbols.txt.zip"
        
        try:
            import requests
            import zipfile
            import io
            
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # Extract zip
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    # Get the txt file inside
                    txt_filename = z.namelist()[0]
                    with z.open(txt_filename) as f:
                        content = f.read().decode('utf-8')
                        
                        # Save to data folder
                        output_file = DATA_DIR / f"{exchange}_instruments.txt"
                        output_file.write_text(content)
                        logger.info(f"✅ Saved {exchange} instruments to {output_file}")
                        
                        # Count lines
                        lines = content.strip().split('\n')
                        logger.info(f"   {len(lines)} instruments")
            else:
                logger.error(f"❌ Failed to download {exchange}: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Error downloading {exchange}: {e}")
    
    # Create metadata file
    metadata = {
        "downloaded_at": datetime.now().isoformat(),
        "exchanges": exchanges
    }
    
    metadata_file = DATA_DIR / "instruments_metadata.json"
    metadata_file.write_text(json.dumps(metadata, indent=2))
    logger.info(f"\n✅ Download complete! Metadata saved to {metadata_file}")

def search_symbol(pattern: str, exchange: str = None):
    """Search for symbols in downloaded instruments"""
    results = []
    
    if exchange:
        exchanges = [exchange]
    else:
        exchanges = ["NSE", "NFO", "BSE", "BFO"]
    
    for exch in exchanges:
        instruments_file = DATA_DIR / f"{exch}_instruments.txt"
        if not instruments_file.exists():
            continue
            
        with open(instruments_file, 'r') as f:
            for line in f:
                if pattern.upper() in line.upper():
                    results.append(f"{exch}: {line.strip()}")
    
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        # Search mode
        if len(sys.argv) < 3:
            print("Usage: python download_instruments.py search <pattern> [exchange]")
            sys.exit(1)
        
        pattern = sys.argv[2]
        exchange = sys.argv[3] if len(sys.argv) > 3 else None
        
        results = search_symbol(pattern, exchange)
        print(f"\nFound {len(results)} results for '{pattern}':\n")
        for r in results[:50]:  # Limit to 50 results
            print(r)
    else:
        # Download mode
        download_instruments()
