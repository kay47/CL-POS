# complete_db_fix.py
import sqlite3
import os
from pathlib import Path

def find_database():
    """Find the database file"""
    # We know it's at instance/pos.db
    db_path = 'instance/pos.db'
    
    if os.path.exists(db_path):
        print(f"Found database at: {db_path}")
        return db_path
    else:
        print(f"Database not found at expected location: {db_path}")
        return None

def fix_database():
    db_path = find_database()
    if not db_path:
        print("No database found. Please check your database location.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current table structure
        print("Checking current sale table structure...")
        cursor.execute("PRAGMA table_info(sale)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"Current columns: {column_names}")
        
        if 'total_profit' not in column_names:
            print("Adding total_profit column...")
            cursor.execute("""
                ALTER TABLE sale 
                ADD COLUMN total_profit NUMERIC(10, 2) NOT NULL DEFAULT 0.00
            """)
            print("✓ total_profit column added")
        else:
            print("✓ total_profit column already exists")
        
        # Update existing records
        print("Updating existing sales with calculated profits...")
        cursor.execute("""
            UPDATE sale 
            SET total_profit = (
                SELECT COALESCE(SUM(
                    (sale_item.price_at_sale - sale_item.cost_at_sale) * sale_item.quantity
                ), 0.0)
                FROM sale_item 
                WHERE sale_item.sale_id = sale.id
            )
            WHERE total_profit = 0.00 OR total_profit IS NULL
        """)
        
        rows_updated = cursor.rowcount
        print(f"✓ Updated {rows_updated} sales records")
        
        # Verify the fix
        cursor.execute("SELECT COUNT(*) FROM sale WHERE total_profit IS NOT NULL")
        count = cursor.fetchone()[0]
        print(f"✓ {count} sales now have profit data")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Database fix completed successfully!")
        print("You can now run your Flask application.")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing database: {e}")
        return False

if __name__ == "__main__":
    print("=== POS Database Fix ===")
    success = fix_database()
    if success:
        print("\nNext steps:")
        print("1. Run your Flask application")
        print("2. Test the POS system")
        print("3. If you want clean migrations later, delete the 'migrations' folder and run 'flask db init'")
    else:
        print("\nManual steps needed:")
        print("1. Locate your .db file")
        print("2. Run this script from the correct directory")