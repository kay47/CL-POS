#!/usr/bin/env python3
"""
Download all CDN assets for offline use
Run this script once while connected to the internet
"""

import os
import requests
from pathlib import Path

# Define assets to download
ASSETS = {
    'static/css/bootstrap.min.css': 'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
    'static/css/bootstrap-icons.css': 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css',
    'static/js/bootstrap.bundle.min.js': 'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js',
    'static/js/chart.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js',
    'static/fonts/bootstrap-icons.woff2': 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/fonts/bootstrap-icons.woff2',
}

def download_file(url, destination):
    """Download a file from URL to destination"""
    print(f"Downloading {url}...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Create directory if it doesn't exist
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(destination, 'wb') as f:
            f.write(response.content)
        
        print(f"✓ Saved to {destination}")
        return True
    except Exception as e:
        print(f"✗ Error downloading {url}: {e}")
        return False

def fix_bootstrap_icons_css():
    """Fix the font path in bootstrap-icons.css"""
    css_file = 'static/css/bootstrap-icons.css'
    if os.path.exists(css_file):
        print("\nFixing font paths in bootstrap-icons.css...")
        with open(css_file, 'r') as f:
            content = f.read()
        
        # Replace CDN font path with local path
        content = content.replace(
            'url("./fonts/bootstrap-icons.woff2',
            'url("../fonts/bootstrap-icons.woff2'
        )
        content = content.replace(
            'url("./fonts/bootstrap-icons.woff"',
            'url("../fonts/bootstrap-icons.woff"'
        )
        
        with open(css_file, 'w') as f:
            f.write(content)
        print("✓ Font paths updated")

def main():
    print("=== POS System Asset Downloader ===\n")
    
    success_count = 0
    total_count = len(ASSETS)
    
    for destination, url in ASSETS.items():
        if download_file(url, destination):
            success_count += 1
    
    # Fix bootstrap icons CSS font path
    fix_bootstrap_icons_css()
    
    print(f"\n{'='*40}")
    print(f"Downloaded {success_count}/{total_count} files successfully")
    
    if success_count == total_count:
        print("\n✓ All assets downloaded! Your POS system will now work offline.")
        print("\nNext steps:")
        print("1. Update your base.html to use local assets")
        print("2. Restart your Flask application")
        print("3. Test offline functionality")
    else:
        print("\n⚠ Some downloads failed. Check errors above and try again.")
    
    print(f"{'='*40}\n")

if __name__ == '__main__':
    main()
