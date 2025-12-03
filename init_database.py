"""
Initialize PostgreSQL database for MY LORD ENTERPRISE POS
Run this script after setting up your external PostgreSQL database
"""
import os
from app import create_app, db
from app.models import User, Product
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def init_database():
    """Initialize database with tables and default data"""
    
    flask_env = os.getenv('FLASK_ENV', 'development')
    app = create_app(flask_env)
    
    with app.app_context():
        print("=" * 60)
        print("🔧 DATABASE INITIALIZATION")
        print("=" * 60)
        
        # Test connection
        try:
            db.engine.connect()
            print("✅ Database connection successful!")
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            host_info = db_uri.split('@')[1].split('/')[0] if '@' in db_uri else 'unknown'
            print(f"📊 Connected to: {host_info}")
        except Exception as e:
            print("❌ Database connection failed!")
            print(f"Error: {str(e)}")
            return
        
        print("\n📋 Creating database tables...")
        
        # Drop all tables (WARNING: This deletes all data!)
        response = input("\n⚠️  WARNING: This will drop all existing tables and data. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Initialization cancelled.")
            return
        
        try:
            # Drop all tables
            db.drop_all()
            print("✅ Dropped existing tables")
            
            # Create all tables
            db.create_all()
            print("✅ Created new tables")
            
            # Create default admin user
            print("\n👤 Creating default admin user...")
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(username='admin', role='admin', is_active=True)
                admin.set_password('admin123')  # Change this password immediately!
                db.session.add(admin)
                db.session.commit()
                print("✅ Default admin user created")
                print("   Username: admin")
                print("   Password: admin123")
                print("   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
            else:
                print("ℹ️  Admin user already exists")
            
            # Create sample products (optional)
            create_samples = input("\n📦 Create sample products? (yes/no): ")
            if create_samples.lower() == 'yes':
                create_sample_products()
            
            print("\n" + "=" * 60)
            print("✅ DATABASE INITIALIZATION COMPLETE!")
            print("=" * 60)
            print("\n🚀 You can now run: python run.py")
            
        except Exception as e:
            print(f"\n❌ Error during initialization: {str(e)}")
            db.session.rollback()

def create_sample_products():
    """Create sample products for testing"""
    sample_products = [
        {
            'name': 'Sample Product 1',
            'category': 'electronics',
            'description': 'Sample electronic product',
            'purchase_price': 50.00,
            'full_price': 75.00,
            'quantity': 100,
            'units_per_pack': 1
        },
        {
            'name': 'Sample Product 2',
            'category': 'food',
            'description': 'Sample food product',
            'purchase_price': 10.00,
            'full_price': 15.00,
            'quantity': 200,
            'units_per_pack': 12
        },
        {
            'name': 'Sample Product 3',
            'category': 'clothing',
            'description': 'Sample clothing item',
            'purchase_price': 30.00,
            'full_price': 50.00,
            'quantity': 50,
            'units_per_pack': 1
        }
    ]
    
    try:
        for product_data in sample_products:
            product = Product.create_with_auto_sku(
                name=product_data['name'],
                category=product_data['category'],
                description=product_data['description'],
                purchase_price=product_data['purchase_price'],
                full_price=product_data['full_price'],
                quantity=product_data['quantity']
            )
            product.units_per_pack = product_data['units_per_pack']
            db.session.add(product)
        
        db.session.commit()
        print(f"✅ Created {len(sample_products)} sample products")
    except Exception as e:
        print(f"❌ Error creating sample products: {str(e)}")
        db.session.rollback()

if __name__ == '__main__':
    init_database()