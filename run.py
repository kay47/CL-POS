import os
from app import create_app
from dotenv import load_dotenv

# 1. Load environment variables first
load_dotenv()

# 2. Initialize the app at the top level so Gunicorn can find it
# Default to 'production' if FLASK_ENV isn't set (standard for Render)
flask_env = os.getenv('FLASK_ENV', 'production')
app = create_app(flask_env)

def check_database_connection():
    """Validates the DB connection; helpful for debugging Render logs."""
    try:
        from app import db
        with app.app_context():
            db.engine.connect()
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False

# 3. Perform a connection check immediately on startup
check_database_connection()

# 4. Local Development Logic
# This block ONLY runs when you type 'python run.py' manually
if __name__ == '__main__':
    import webbrowser
    import threading
    
    BASE_URL = "http://127.0.0.1:5000/"
    
    def open_browser():
        """Opens the browser for local convenience."""
        webbrowser.open_new(BASE_URL)

    print("=" * 60)
    print("🚀 MY LORD ENTERPRISE POS SYSTEM (Local Mode)")
    print(f"Environment: {flask_env}")
    print("=" * 60)
    
    # Only open the browser if we aren't in a reloader subprocess
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        threading.Timer(1.25, open_browser).start()
    
    # Run using the Flask development server
    app.run(debug=True, host='0.0.0.0', port=5000)