import os
import webbrowser
import threading
from app import create_app
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the URL your app runs on
BASE_URL = "http://127.0.0.1:5000/"

# Get Flask environment from environment variable
flask_env = os.getenv('FLASK_ENV', 'development')
app = create_app(flask_env)

def open_browser():
    """Opens the default web browser to the app's URL after a short delay."""
    webbrowser.open_new(BASE_URL)

def check_database_connection():
    """Check if database connection is working"""
    try:
        from app import db
        with app.app_context():
            # Try to execute a simple query
            db.engine.connect()
            print("✅ Database connection successful!")
            print(f"📊 Connected to: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1] if '@' in app.config['SQLALCHEMY_DATABASE_URI'] else 'database'}")
            return True
    except Exception as e:
        print("❌ Database connection failed!")
        print(f"Error: {str(e)}")
        print("\n📝 Please check your database configuration in .env file")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 MY LORD ENTERPRISE POS SYSTEM")
    print("=" * 60)
    print(f"Environment: {flask_env}")
    print(f"Debug Mode: {app.config['DEBUG']}")
    
    # Check database connection before starting
    if check_database_connection():
        # Check if the application is NOT in reloader mode
        is_reloader = False
        try:
            from werkzeug.serving import is_running_from_reloader
            is_reloader = is_running_from_reloader()
        except ImportError:
            pass 
            
        if not is_reloader:
            print(f"\n🌐 Server starting on {BASE_URL}")
            print("📂 Opening browser in 1.25 seconds...")
            threading.Timer(1.25, open_browser).start()
        
        print("=" * 60)
        # Run the Flask app
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("\n⚠️  Cannot start server - database connection required")
        print("=" * 60)