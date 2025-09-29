from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user

def admin_required(func):
    """Decorator to require admin role for access to views"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('auth.login'))
        # Check if password change is required
        if current_user.needs_password_change():
            flash('You must change your temporary password before accessing this page.', 'warning')
            return redirect(url_for('auth.change_password'))
        
        if current_user.role != 'admin':
            flash('Access denied. Administrator access required.', 'error')
            return redirect(url_for('main.index'))
        return func(*args, **kwargs)
    return wrapper

def manager_required(func):
    """Decorator to require manager or admin role for access to views"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('auth.login'))
        
        # Check if password change is required
        if current_user.needs_password_change():
            flash('You must change your temporary password before accessing this page.', 'warning')
            return redirect(url_for('auth.change_password'))
        
        if current_user.role not in ['manager', 'admin']:
            flash('Access denied. Manager access required.', 'error')
            return redirect(url_for('main.index'))
        return func(*args, **kwargs)
    return wrapper

def cashier_required(func):
    """Decorator to require cashier role for access to views"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('auth.login'))
        
        # Check if password change is required
        if current_user.needs_password_change():
            flash('You must change your temporary password before accessing this page.', 'warning')
            return redirect(url_for('auth.change_password'))
        
        if current_user.role not in ['clerk', 'cashier', 'manager', 'admin']:
            flash('Access denied. Cashier privileges required.', 'error')
            return redirect(url_for('main.index'))
        return func(*args, **kwargs)
    return wrapper

def password_change_required(func):
    """Decorator to ensure user has changed temporary password"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('auth.login'))
        
        # Check if password change is required
        if current_user.needs_password_change():
            flash('You must change your temporary password before accessing this page.', 'warning')
            return redirect(url_for('auth.change_password'))
        
        return func(*args, **kwargs)
    return wrapper

def role_required(roles):
    """
    Decorator to require specific roles for access to views.
    
    Args:
        roles: A list of role names or individual role arguments that can access the view
    
    Usage:
        @role_required(['admin', 'manager'])
        or
        @role_required('admin')
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'info')
                return redirect(url_for('auth.login'))
            
            # Check if password change is required
            if current_user.needs_password_change():
                flash('You must change your temporary password before accessing this page.', 'warning')
                return redirect(url_for('auth.change_password'))
            
            # Handle both single role and list of roles
            if isinstance(roles, str):
                allowed_roles = [roles]
            elif isinstance(roles, (list, tuple)):
                allowed_roles = list(roles)
            else:
                # Handle the case where roles might be passed as *args
                allowed_roles = [roles] if roles else []
            
            if current_user.role not in allowed_roles:
                flash(f'Access denied. Required roles: {", ".join(allowed_roles)}', 'error')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

def api_key_required(f):
    """Decorator for API endpoints that require authentication"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)

         # For API endpoints, we might want to allow access even with temp passwords
        # but return a different response indicating password change is needed
        return f(*args, **kwargs)
    return wrapper