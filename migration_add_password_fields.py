# migration_add_password_fields.py
"""
Database migration to add temporary password fields to User model
Run this script to update your existing database schema
"""

from app import db
from flask import current_app
from sqlalchemy import text

def migrate_user_table():
    """Add new columns to User table for temporary password functionality"""
    
    try:
        with db.engine.connect() as conn:
            # Add new columns to user table
            migration_queries = [
                # Add temporary password flag
                "ALTER TABLE user ADD COLUMN is_temporary_password BOOLEAN DEFAULT FALSE NOT NULL",
                
                # Add password reset token
                "ALTER TABLE user ADD COLUMN password_reset_token VARCHAR(100)",
                
                # Add password reset expiry
                "ALTER TABLE user ADD COLUMN password_reset_expires DATETIME",
                
                # Add must change password flag
                "ALTER TABLE user ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE NOT NULL",
                
                # Add last password change timestamp
                "ALTER TABLE user ADD COLUMN last_password_change DATETIME"
            ]
            
            for query in migration_queries:
                try:
                    conn.execute(text(query))
                    print(f"✓ Executed: {query}")
                except Exception as e:
                    # Generic handling for column already exists in SQLite/SQLAlchemy
                    if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                        print(f"⚠ Column already exists, skipping: {query}")
                    else:
                        print(f"✗ Error executing: {query}")
                        print(f"  Error: {e}")
            
            conn.commit()
            print("\n✓ Migration completed successfully!")
            
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False
    
    return True

def update_existing_users():
    """Update existing users to set default values"""
    try:
        from app.models import User
        
        # Update all existing users
        users = User.query.all()
        
        for user in users:
            # Note: Checking for 'is None' handles cases where the column was just added 
            # but default values weren't applied to existing rows by the DB engine
            if user.is_temporary_password is None:
                user.is_temporary_password = False
            if user.must_change_password is None:
                user.must_change_password = False
            if user.last_password_change is None:
                # Set to creation date or current time if creation date not available
                user.last_password_change = user.created_at if hasattr(user, 'created_at') and user.created_at else db.func.current_timestamp()
        
        db.session.commit()
        print(f"✓ Updated {len(users)} existing users with default values")
        
    except Exception as e:
        print(f"✗ Failed to update existing users: {e}")
        db.session.rollback()
        return False
    
    return True

def create_initial_admin():
    """Create initial admin user if none exists"""
    try:
        from app.models import User
        
        admin_user = User.query.filter_by(role='admin').first()
        
        if not admin_user:
            # Create default admin user
            admin = User(
                username='admin',
                role='admin',
                is_active=True
            )
            # The .set_password method must be updated in models.py to accept is_temporary
            admin.set_password('admin123', is_temporary=True)  # Force password change
            
            db.session.add(admin)
            db.session.commit()
            
            print("✓ Created default admin user (username: admin, password: admin123)")
            print("⚠ Admin user has temporary password and must change it on first login")
        else:
            print("✓ Admin user already exists")
            
    except Exception as e:
        print(f"✗ Failed to create admin user: {e}")
        db.session.rollback()
        return False
    
    return True

if __name__ == '__main__':
    # Run migration
    print("Starting database migration for temporary password features...")
    print("=" * 60)
    
    # --- FIX: APPLICATION CONTEXT ERROR ---
    try:
        # 1. Attempt to import the Flask application instance 'app'
        from run import app 
        
        # 2. Execute all database operations within the application context
        with app.app_context():
            if migrate_user_table():
                if update_existing_users():
                    if create_initial_admin():
                        print("\n" + "=" * 60)
                        print("✓ ALL MIGRATION STEPS COMPLETED SUCCESSFULLY!")
                        print("\nNext steps:")
                        print("1. Update your models.py with the new User model")
                        print("2. Update your forms.py with the new forms")
                        print("3. Update your auth.py routes")
                        print("4. Add the new HTML templates")
                        print("5. Update your decorators.py")
                        print("\nDefault admin credentials:")
                        print("Username: admin")
                        print("Password: admin123 (temporary - must be changed on first login)")
                    else:
                        print("\n✗ Failed to create initial admin user")
                else:
                    print("\n✗ Failed to update existing users")
            else:
                print("\n✗ Database migration failed")
        
    except ImportError:
        print("\n✗ Migration failed: Could not import 'app'. Ensure your Flask application instance is named 'app' and is correctly defined and importable from the 'app' module.")
    except Exception as e:
        print(f"\n✗ Migration failed unexpectedly during context execution: {e}")
    # --- END FIX ---