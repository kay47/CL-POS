"""
Database Migration Script
Adds missing columns to Product and Expense tables
Run this script once to update your database schema
"""

from app import db, create_app # 💡 FIX: Import create_app instead of app
from sqlalchemy import text
import os

def migrate_database():
    """Add new columns to existing tables"""
    
    # 💡 FIX: Create the app instance and run the script within its context
    app = create_app(os.getenv('FLASK_ENV') or 'development')
    
    with app.app_context():
        connection = db.engine.connect()
        
        print("Starting database migration...")
        
        try:
            # Check if Product table exists and add missing columns
            print("\n--- Migrating Product table ---")
            
            # Add image_filename column
            try:
                connection.execute(text(
                    "ALTER TABLE product ADD COLUMN image_filename VARCHAR(255)"
                ))
                print("✓ Added image_filename column to Product table")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("- image_filename column already exists")
                else:
                    print(f"✗ Error adding image_filename: {e}")
            
            # Add image_path column
            try:
                connection.execute(text(
                    "ALTER TABLE product ADD COLUMN image_path VARCHAR(500)"
                ))
                print("✓ Added image_path column to Product table")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("- image_path column already exists")
                else:
                    print(f"✗ Error adding image_path: {e}")

            # Check if Expense table exists and add missing columns
            print("\n--- Migrating Expense table ---")
            
            # Add document_filename column
            try:
                connection.execute(text(
                    "ALTER TABLE expense ADD COLUMN document_filename VARCHAR(255)"
                ))
                print("✓ Added document_filename column to Expense table")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("- document_filename column already exists")
                else:
                    print(f"✗ Error adding document_filename: {e}")
            
            # Add document_path column
            try:
                connection.execute(text(
                    "ALTER TABLE expense ADD COLUMN document_path VARCHAR(500)"
                ))
                print("✓ Added document_path column to Expense table")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("- document_path column already exists")
                else:
                    print(f"✗ Error adding document_path: {e}")
            
            # Add document_type column
            try:
                connection.execute(text(
                    "ALTER TABLE expense ADD COLUMN document_type VARCHAR(100)"
                ))
                print("✓ Added document_type column to Expense table")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("- document_type column already exists")
                else:
                    print(f"✗ Error adding document_type: {e}")
            
            # Commit the changes
            connection.commit()
            print("\n✓ Migration completed successfully!")
            
            # Create necessary directories
            print("\n--- Creating upload directories ---")
            directories = [
                'static/uploads/product_images',
                'static/uploads/expense_documents',
                'static/images'
            ]
            
            for directory in directories:
                # Use os.path.join for cross-platform compatibility
                full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', directory)
                os.makedirs(full_path, exist_ok=True)
                print(f"✓ Created/verified directory: {directory}")
            
            print("\n✓ All migrations completed successfully!")
            print("\nYou can now run your application.")
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            connection.rollback()
        finally:
            connection.close()

if __name__ == "__main__":
    migrate_database()