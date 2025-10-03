"""
Migration script to add retail units support to Product table
Run this once to update your database schema
"""

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Starting migration: Adding retail units columns...")
    
    try:
        # Check if columns already exist
        result = db.session.execute(text("PRAGMA table_info(product)"))
        columns = [row[1] for row in result.fetchall()]
        
        print(f"Existing columns: {columns}")
        
        # Add units_per_pack column if it doesn't exist
        if 'units_per_pack' not in columns:
            print("Adding units_per_pack column...")
            db.session.execute(text(
                "ALTER TABLE product ADD COLUMN units_per_pack INTEGER DEFAULT 1 NOT NULL"
            ))
            db.session.commit()
            print("✓ Added units_per_pack column")
        else:
            print("✓ units_per_pack column already exists")
        
        # Add unit_price column if it doesn't exist
        if 'unit_price' not in columns:
            print("Adding unit_price column...")
            db.session.execute(text(
                "ALTER TABLE product ADD COLUMN unit_price NUMERIC(10, 2)"
            ))
            db.session.commit()
            print("✓ Added unit_price column")
        else:
            print("✓ unit_price column already exists")
        
        # Add quarter_price column if it doesn't exist (if not already there)
        if 'quarter_price' not in columns:
            print("Adding quarter_price column...")
            db.session.execute(text(
                "ALTER TABLE product ADD COLUMN quarter_price NUMERIC(10, 2)"
            ))
            db.session.commit()
            print("✓ Added quarter_price column")
        else:
            print("✓ quarter_price column already exists")
        
        # Update existing products to have default values
        print("\nUpdating existing products with default values...")
        
        # Set units_per_pack = 1 for all existing products (if needed)
        db.session.execute(text(
            "UPDATE product SET units_per_pack = 1 WHERE units_per_pack IS NULL OR units_per_pack = 0"
        ))
        
        # Auto-calculate unit_price based on full_price and units_per_pack
        db.session.execute(text(
            "UPDATE product SET unit_price = full_price / units_per_pack WHERE unit_price IS NULL"
        ))
        
        # Auto-calculate quarter_price as 25% of full_price
        db.session.execute(text(
            "UPDATE product SET quarter_price = full_price / 4 WHERE quarter_price IS NULL"
        ))
        
        db.session.commit()
        
        print("✓ Updated existing products")
        
        # Verify the migration
        print("\nVerifying migration...")
        result = db.session.execute(text("PRAGMA table_info(product)"))
        columns = [row[1] for row in result.fetchall()]
        
        required_columns = ['units_per_pack', 'unit_price', 'quarter_price']
        missing = [col for col in required_columns if col not in columns]
        
        if missing:
            print(f"⚠ WARNING: Missing columns: {missing}")
        else:
            print("✓ All required columns present")
        
        # Show sample data
        print("\nSample product data:")
        result = db.session.execute(text(
            "SELECT sku, name, full_price, half_price, quarter_price, units_per_pack, unit_price "
            "FROM product LIMIT 3"
        ))
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]}")
            print(f"    Full: {row[2]}, Half: {row[3]}, Quarter: {row[4]}")
            print(f"    Units/Pack: {row[5]}, Unit Price: {row[6]}")
        
        print("\n✓ Migration completed successfully!")
        print("\nYou can now restart your application.")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n✗ Migration failed: {str(e)}")
        print("\nIf you see 'duplicate column name' errors, the columns may already exist.")
        print("You can safely ignore those errors.")
        raise

print("\n" + "="*60)
print("Migration script finished")
print("="*60)