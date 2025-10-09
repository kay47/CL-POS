from flask import Flask, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import config
from decimal import Decimal
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Import models after db initialization
    from app.models import User, Product, Sale, SaleItem
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    '''@app.template_filter('currency')
    def format_currency(value):
        """Format a number as currency"""
        if value is None:
            return "GHS 0.00"
        
        # Handle different number types
        if isinstance(value, (int, float, Decimal)):
            return f"GHS {float(value):,.2f}"
        
        # Try to convert string to float
        try:
            return f"GHS {float(value):,.2f}"
        except (ValueError, TypeError):
            return "GHS 0.00"'''
    
     #Register custom Jinja2 filters for money formatting
    @app.template_filter('currency')
    def currency_filter(value):
        """Format number as currency with thousand separators (2 decimal places)"""
        try:
            if value is None:
                return "0.00"
            num_value = float(value)
            return "{:,.2f}".format(num_value)
        except (ValueError, TypeError):
            return "0.00"
    
    # Add alias for backward compatibility
    @app.template_filter('format_currency')
    def format_currency_filter(value):
        """Alias for currency filter"""
        return currency_filter(value)
    
    @app.template_filter('number')
    def number_filter(value):
        """Format whole numbers with thousand separators"""
        try:
            if value is None:
                return "0"
            num_value = int(float(value))  # Handle decimal values
            return "{:,}".format(num_value)
        except (ValueError, TypeError):
            return "0"
        
    # Add this route to serve uploaded images
    @app.route('/static/uploads/product_images/<filename>')
    def uploaded_file(filename):
        upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'product_images')
        return send_from_directory(upload_folder, filename)    
    
    # Alternative name that matches your template usage
    app.jinja_env.filters['format_currency'] = currency_filter

    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.products import bp as products_bp
    app.register_blueprint(products_bp, url_prefix='/products')
    
    from app.pos import bp as pos_bp
    app.register_blueprint(pos_bp, url_prefix='/pos')
    
    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    from app.expenses import bp as expenses_bp
    app.register_blueprint(expenses_bp, url_prefix='/expenses')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    # Add the health check endpoint
    @app.route('/health')
    def health_check():
        return 'OK', 200
    
    # Context processors
    @app.context_processor
    def utility_processor():
        def format_currency(amount):
            return f"${amount:.2f}" if amount else "$0.00"
        
        return dict(format_currency=format_currency)
    
    # Create tables and default user
    with app.app_context():
        db.create_all()
        
        # Create default admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created: admin/admin123")
    
    return app