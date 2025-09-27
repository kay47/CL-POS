from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.forms import LoginForm, RegisterForm
from app.decorators import admin_required, manager_required
from app import db
from app.models import User, Sale  # Add Sale import
from app.forms import LoginForm, RegisterForm, EditUserForm  # Add EditUserForm import

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.index')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page)
        flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html', form=form)

@bp.route('/register', methods=['GET', 'POST'])
@login_required
@admin_required
@manager_required
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'User {user.username} has been registered successfully!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('auth/register.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/users')
@login_required
@admin_required
def manage_users():
    """List all users with management options"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    users = User.query.paginate(
        page=page, 
        per_page=per_page,
        error_out=False
    )
    
    return render_template('auth/manage_users.html', users=users)

@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user details"""
    user = User.query.get_or_404(user_id)
    
    # Prevent editing the current admin user's role to avoid lockout
    if user.id == current_user.id and user.role == 'admin':
        flash('You cannot modify your own admin account to prevent lockout.', 'warning')
        return redirect(url_for('auth.manage_users'))
    
    form = EditUserForm(obj=user)
    
    if form.validate_on_submit():
        # Check if username is being changed and if new username already exists
        if form.username.data != user.username:
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user:
                flash('Username already exists. Please choose a different username.', 'error')
                return render_template('auth/edit_user.html', form=form, user=user)
        
        # Update user details
        user.username = form.username.data
        user.role = form.role.data
        
        # Update password if provided
        if form.password.data:
            user.set_password(form.password.data)
        
        try:
            db.session.commit()
            flash(f'User {user.username} has been updated successfully!', 'success')
            return redirect(url_for('auth.manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'error')
    
    return render_template('auth/edit_user.html', form=form, user=user)

@bp.route('/users/<int:user_id>/delete/confirm')
@login_required
@admin_required
def confirm_delete_user(user_id):
    """Show confirmation page before deleting user"""
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting the current admin user
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    # Check if user has any sales
    sales_count = Sale.query.filter_by(clerk_id=user.id).count()
    
    return render_template('auth/confirm_delete_user.html', user=user, sales_count=sales_count)

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user"""
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting the current admin user
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    # Check if this is the last admin user
    admin_count = User.query.filter_by(role='admin').count()
    if user.role == 'admin' and admin_count <= 1:
        flash('Cannot delete the last admin user. System must have at least one admin.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    try:
        username = user.username
        
        # Check if user has sales - you might want to handle this differently
        sales_count = Sale.query.filter_by(clerk_id=user.id).count()
        if sales_count > 0:
            # Option 1: Prevent deletion
            flash(f'Cannot delete user {username}. User has {sales_count} associated sales. Consider deactivating instead.', 'error')
            return redirect(url_for('auth.manage_users'))
            
            # Option 2: Set sales clerk_id to NULL (uncomment if preferred)
            # Sale.query.filter_by(clerk_id=user.id).update({'clerk_id': None})
        
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User {username} has been deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('auth.manage_users'))

@bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Toggle user active/inactive status (if you have this field)"""
    user = User.query.get_or_404(user_id)
    
    # Prevent deactivating the current admin user
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    try:
        # Assuming you have an 'is_active' field in your User model
        # If not, you can add it or skip this function
        if hasattr(user, 'is_active'):
            user.is_active = not user.is_active
            db.session.commit()
            
            status = 'activated' if user.is_active else 'deactivated'
            flash(f'User {user.username} has been {status}!', 'success')
        else:
            flash('User status toggle not available.', 'info')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating user status: {str(e)}', 'error')
    
    return redirect(url_for('auth.manage_users'))

