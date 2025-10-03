# Create this file as: migrations/add_retail_units.py
# Run it once to update your database

from app import db, create_app
from app.models import Product
from decimal import Decimal

def migrate_database():
    """Add retail unit fields to existing products"""
    app = create_app()
    
    with app.app_context():
        print("Starting database migration...")
        
        # Add columns to database (if using SQLAlchemy migrations, this would be in alembic)
        # For SQLite, you might need to add columns manually or use ALTER TABLE
        
        try:
            # Check if columns exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('product')]
            
            if 'units_per_pack' not in columns:
                print("Adding units_per_pack column...")
                db.session.execute('ALTER TABLE product ADD COLUMN units_per_pack INTEGER DEFAULT 1 NOT NULL')
            
            if 'unit_price' not in columns:
                print("Adding unit_price column...")
                db.session.execute('ALTER TABLE product ADD COLUMN unit_price NUMERIC(10, 2)')
            
            if 'image_filename' not in columns:
                print("Adding image_filename column...")
                db.session.execute('ALTER TABLE product ADD COLUMN image_filename VARCHAR(255)')
            
            if 'image_path' not in columns:
                print("Adding image_path column...")
                db.session.execute('ALTER TABLE product ADD COLUMN image_path VARCHAR(500)')
            
            db.session.commit()
            print("Database schema updated successfully!")
            
            # Update existing products with default values
            print("\nUpdating existing products...")
            products = Product.query.all()
            
            for product in products:
                # Set default units_per_pack if not set
                if not hasattr(product, 'units_per_pack') or product.units_per_pack is None:
                    product.units_per_pack = 1
                
                # Calculate unit_price if not set
                if not hasattr(product, 'unit_price') or product.unit_price is None:
                    if product.full_price and product.units_per_pack:
                        product.unit_price = product.full_price / Decimal(str(product.units_per_pack))
                    else:
                        product.unit_price = product.full_price
                
                print(f"Updated: {product.sku} - {product.name} (Units/pack: {product.units_per_pack}, Unit price: {product.unit_price})")
            
            db.session.commit()
            print(f"\nMigration completed! Updated {len(products)} products.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_database()