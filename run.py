import os
from app import create_app
from dotenv import load_dotenv

# Load .env only if it exists (local dev)
load_dotenv()

# Initialize the app at the top level so Gunicorn can find it
# Render uses the 'FLASK_ENV' or 'NODE_ENV' usually, but we'll default to 'production'
flask_env = os.getenv('FLASK_ENV', 'production')
app = create_app(flask_env)

def check_db():
    """Verify DB on startup without crashing the import if possible"""
    try:
        from app import db
        with app.app_context():
            db.engine.connect()
            print("✅ Database connection successful!")
    except Exception as e:
        print(f"⚠️ Database connection warning: {e}")
        # We don't exit(1) here so we can see more logs from Gunicorn

# Run a quick check
check_db()

if __name__ == '__main__':
    # This section is ONLY for running 'python run.py' locally
    import webbrowser
    import threading

    def open_browser():
        webbrowser.open_new("http://127.0.0.1:5000/")

    print("🚀 Starting local development server...")
    threading.Timer(1.25, open_browser).start()
    
    # Local dev server
    app.run(debug=True, host='0.0.0.0', port=5000)