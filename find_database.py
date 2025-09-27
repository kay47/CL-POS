# find_database.py
import os
from pathlib import Path

def find_database():
    print("Searching for database files...")
    print("=" * 50)
    
    # Common database locations
    possible_locations = [
        'app.db',
        'database.db',
        'pos.db',
        'instance/app.db',
        'instance/database.db',
        'app/app.db',
        'app/database.db'
    ]
    
    found_databases = []
    
    # Check common locations first
    print("Checking common locations:")
    for location in possible_locations:
        if os.path.exists(location):
            size = os.path.getsize(location)
            print(f"  ✓ Found: {location} ({size} bytes)")
            found_databases.append(location)
        else:
            print(f"  ✗ Not found: {location}")
    
    print("\nSearching all .db files in current directory and subdirectories:")
    # Search for all .db files
    for db_file in Path('.').rglob('*.db'):
        abs_path = str(db_file)
        size = os.path.getsize(abs_path)
        print(f"  Found: {abs_path} ({size} bytes)")
        if abs_path not in found_databases:
            found_databases.append(abs_path)
    
    print("\nSearching for SQLite files (common patterns):")
    for pattern in ['*.sqlite', '*.sqlite3', '*.db3']:
        for file in Path('.').rglob(pattern):
            abs_path = str(file)
            size = os.path.getsize(abs_path)
            print(f"  Found: {abs_path} ({size} bytes)")
            if abs_path not in found_databases:
                found_databases.append(abs_path)
    
    print("\n" + "=" * 50)
    if found_databases:
        print(f"Summary: Found {len(found_databases)} database file(s)")
        for i, db in enumerate(found_databases, 1):
            print(f"  {i}. {db}")
    else:
        print("No database files found!")
        print("Your Flask app may create the database when it first runs.")
        print("Try running your Flask app first, then run this script again.")
    
    return found_databases

if __name__ == "__main__":
    find_database()