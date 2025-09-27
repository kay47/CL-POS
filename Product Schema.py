# migration_script.py
# Run this script to update your database schema for the new pricing model

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app import create_app, db
from app.models import Product

def migrate_product_pricing():
    """
    Migration script to update existing products for the new pricing model.
    This script will:
    1. Remove the separate half_price and quarter_price columns (if they exist)
    2. Ensure all products have the full_price field populated
    3. Update the price field to match full_price for backward compatibility
    """
    
    app = create_app()
    
    with app.app_context():
        print("Starting pricing model migration...")
        
        try:
            # Get all products
            products = Product.query.all()
            print(f"Found {len(products)} products to update")
            
            for product in products:
                # Ensure full_price is set (use existing price if full_price is not set)
                if not hasattr(product, 'full_price') or not product.full_price:
                    if hasattr(product, 'price') and product.price:
                        product.full_price = product.price
                        print(f"Set full_price for {product.name}: GHS {product.full_price}")
                    else:
                        # Default to purchase_price * 1.3 if no price is set
                        product.full_price = float(product.purchase_price) * 1.3
                        print(f"Auto-calculated full_price for {product.name}: GHS {product.full_price}")
                
                # Ensure price field matches full_price for backward compatibility
                product.price = product.full_price
                
            # Commit changes
            db.session.commit()
            print("✅ Migration completed successfully!")
            
            # Verify the migration
            print("\n--- Verification ---")
            for product in products:
                half_price = float(product.full_price) * 0.5
                quarter_price = float(product.full_price) * 0.25
                full_profit = float(product.full_price) - float(product.purchase_price)
                half_profit = full_profit * 0.5
                quarter_profit = full_profit * 0.25
                
                print(f"\n{product.name}:")
                print(f"  Purchase Price: GHS {product.purchase_price}")
                print(f"  Full Pack: GHS {product.full_price} (Profit: GHS {full_profit:.2f})")
                print(f"  Half Pack: GHS {half_price:.2f} (Profit: GHS {half_profit:.2f})")
                print(f"  Quarter Pack: GHS {quarter_price:.2f} (Profit: GHS {quarter_profit:.2f})")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

def update_database_schema():
    """
    Update the database schema by dropping old columns if they exist
    """
    app = create_app()
    
    with app.app_context():
        print("Updating database schema...")
        
        try:
            # Drop old columns if they exist
            with db.engine.connect() as conn:
                # Check if half_price column exists and drop it
                try:
                    conn.execute(db.text("ALTER TABLE product DROP COLUMN half_price"))
                    print("Dropped half_price column")
                except Exception:
                    print("half_price column doesn't exist or already dropped")
                
                # Check if quarter_price column exists and drop it
                try:
                    conn.execute(db.text("ALTER TABLE product DROP COLUMN quarter_price"))
                    print("Dropped quarter_price column")
                except Exception:
                    print("quarter_price column doesn't exist or already dropped")
                
                conn.commit()
            
            print("✅ Schema update completed!")
            
        except Exception as e:
            print(f"❌ Schema update failed: {str(e)}")
            raise

if __name__ == "__main__":
    print("=" * 50)
    print("PRODUCT PRICING MODEL MIGRATION")
    print("=" * 50)
    print("This script will update your products to use the new fractional pricing model.")
    print("New model:")
    print("- Full Pack: Manual entry")
    print("- Half Pack: 50% of Full Pack price")
    print("- Quarter Pack: 25% of Full Pack price")
    print("- Half Pack Profit: 50% of Full Pack profit")
    print("- Quarter Pack Profit: 25% of Full Pack profit")
    print()
    
    confirm = input("Do you want to proceed? (yes/no): ").lower().strip()
    
    if confirm in ['yes', 'y']:
        try:
            # First, update existing product data
            migrate_product_pricing()
            
            # Then update the schema (optional - only if you have old columns)
            schema_update = input("\nDo you want to remove old half_price and quarter_price columns? (yes/no): ").lower().strip()
            if schema_update in ['yes', 'y']:
                update_database_schema()
            
            print("\n🎉 Migration completed successfully!")
            print("Your products now use the new fractional pricing model.")
            
        except Exception as e:
            print(f"\n💥 Migration failed: {str(e)}")
            print("Please check your database and try again.")
            
    else:
        print("Migration cancelled.")