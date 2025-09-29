import os
import webbrowser
import threading
from app import create_app

# Define the URL your app runs on
BASE_URL = "http://127.0.0.1:5000/"

app = create_app(os.getenv('FLASK_ENV') or 'development')

def open_browser():
    """Opens the default web browser to the app's URL after a short delay."""
    webbrowser.open_new(BASE_URL)

if __name__ == '__main__':
    # 💡 FIX: Check if the application is NOT in reloader mode.
    # The 'werkzeug.serving.is_running_from_reloader' function is the most reliable check.
    # We must access the app.is_reloader_process attribute after the app is initialized.
    
    # Check if we are running in the main process (not the reloader)
    is_reloader = False
    try:
        # This checks if the reloader is active. If Flask changes, 
        # it will be in app.run's process, but we can check the environment.
        from werkzeug.serving import is_running_from_reloader
        is_reloader = is_running_from_reloader()
    except ImportError:
        # Fallback for older Flask/Werkzeug versions (less reliable)
        pass 
        
    if not is_reloader:
        # Start a new thread to open the browser only in the main process
        # The delay gives the Flask server a moment to start up and bind to the port
        print(f"Server starting on {BASE_URL}. Opening browser in 1.25 seconds...")
        threading.Timer(1.25, open_browser).start()
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)