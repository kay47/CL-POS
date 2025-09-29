from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.forms import LoginForm, RegisterForm, ForgotPasswordForm, FirstTimePasswordChangeForm, ChangePasswordForm, ResetPasswordForm
from app.decorators import admin_required, manager_required
from app import db
from app.models import User, Sale  # Add Sale import
from app.forms import LoginForm, RegisterForm, EditUserForm  # Add EditUserForm import

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Check if user needs to change password
        if current_user.needs_password_change():
            return redirect(url_for('auth.change_password'))
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'error')
                return render_template('auth/login.html', form=form)
            
            login_user(user, remember=True)
            # Check if user needs to change password
            if user.needs_password_change():
                flash('You must change your temporary password before continuing.', 'warning')
                return redirect(url_for('auth.change_password'))
            
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
        # Generate temporary password
        temp_password = User.generate_temporary_password()

        user = User(
            username=form.username.data,
            role=form.role.data,
            is_active=True
        )

        # Set as temporary password
        user.set_password(temp_password, is_temporary=True)

        db.session.add(user)
        db.session.commit()

        # Store temporary password in session for display
        session['temp_password_info'] = {
            'username': user.username,
            'password': temp_password
        }    

        flash(f'User {user.username} has been created successfully!', 'success')
        return redirect(url_for('auth.show_temp_password'))
    
    return render_template('auth/register.html', form=form)

@bp.route('/temp-password')
@login_required
@admin_required
def show_temp_password():
    """Display temporary password to admin after user creation"""
    temp_info = session.pop('temp_password_info', None)
    if not temp_info:
        flash('No temporary password information found.', 'error')
        return redirect(url_for('auth.manage_users'))
    
    return render_template('auth/temp_password.html', 
                         username=temp_info['username'],
                         temp_password=temp_info['password'])

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Handle password change for users with temporary passwords or regular users"""
    
    # If user has temporary password, use FirstTimePasswordChangeForm
    if current_user.is_temporary_password:
        form = FirstTimePasswordChangeForm()
        form.username.data = current_user.username
        
        if form.validate_on_submit():
            # Verify temporary password
            if not current_user.check_password(form.temporary_password.data):
                flash('Invalid temporary password.', 'error')
                return render_template('auth/change_password.html', form=form, is_first_time=True)
            
            # Update to new password
            current_user.complete_password_change(form.new_password.data)
            db.session.commit()
            
            flash('Password changed successfully! You can now use the system normally.', 'success')
            return redirect(url_for('main.index'))
        
        return render_template('auth/change_password.html', form=form, is_first_time=True)
    
    else:
        # Regular password change
        form = ChangePasswordForm()
        
        if form.validate_on_submit():
            current_user.complete_password_change(form.new_password.data)
            db.session.commit()
            
            flash('Password changed successfully!', 'success')
            return redirect(url_for('main.index'))
        
        return render_template('auth/change_password.html', form=form, is_first_time=False)

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle password reset requests"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.is_active:
            # Generate reset token
            token = user.generate_password_reset_token()
            db.session.commit()
            
            # In a real application, you would send an email with the reset link
            # For now, we'll show the token (you should implement email sending)
            session['reset_token_info'] = {
                'username': user.username,
                'token': token
            }
            
            flash('Password reset instructions have been generated. Please contact an administrator.', 'info')
            # In production, redirect to a "check your email" page
            return redirect(url_for('auth.show_reset_token'))  # Temporary for demo
        else:
            # Don't reveal if user exists or not
            flash('If the username exists and is active, password reset instructions will be sent.', 'info')
    
    return render_template('auth/forgot_password.html', form=form)

@bp.route('/reset-token')
def show_reset_token():
    """Temporary route to show reset token (replace with email in production)"""
    token_info = session.pop('reset_token_info', None)
    if not token_info:
        flash('No reset token information found.', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_token.html', 
                         username=token_info['username'],
                         token=token_info['token'])

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset with token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # Find user with this token
    user = User.query.filter_by(password_reset_token=token).first()
    
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    form.token.data = token
    
    if form.validate_on_submit():
        user.complete_password_change(form.new_password.data)
        db.session.commit()
        
        flash('Your password has been reset successfully! Please log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)

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
        
        # Handle password reset
        if form.reset_password.data:
            temp_password = User.generate_temporary_password()
            user.set_password(temp_password, is_temporary=True)

            # Store for display
            session['temp_password_info'] = {
                'username': user.username,
                'password': temp_password
            }
            
            flash(f'User {user.username} password has been reset to a temporary password.', 'warning')
        
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

