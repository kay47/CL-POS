# simple_migration.py
import sqlite3
import os

def find_database():
    """Find the SQLite database file"""
    possible_paths = [
        'app.db',
        'database.db',
        'instance/app.db', 
        'instance/database.db',
        'pos.db',
        'data.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # If not found, list all .db files
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.db'):
                return os.path.join(root, file)
    
    return None

def migrate_database():
    db_path = find_database()
    
    if not db_path:
        print("No SQLite database found. Please specify the database path manually.")
        return False
    
    print(f"Using database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(user);")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Current user table columns: {columns}")
        
        if 'is_active' not in columns:
            print("Adding is_active column...")
            cursor.execute("ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1;")
            cursor.execute("UPDATE user SET is_active = 1 WHERE is_active IS NULL;")
            conn.commit()
            print("✓ Migration completed!")
        else:
            print("✓ is_active column already exists")
        
        # Show current users
        cursor.execute("SELECT id, username, role, is_active FROM user;")
        users = cursor.fetchall()
        print("\nCurrent users:")
        for user in users:
            print(f"  ID: {user[0]}, Username: {user[1]}, Role: {user[2]}, Active: {user[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    migrate_database()