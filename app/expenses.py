from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from app.models import Expense
from app.forms import ExpenseForm, ExpenseEditForm
from app.decorators import manager_required
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from werkzeug.utils import secure_filename
import os

bp = Blueprint('expenses', __name__)

# Configure upload folder - FIXED PATH HANDLING
# Get the base directory of your app
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'expense_documents')

# Create the directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

print(f"Expense documents upload folder: {UPLOAD_FOLDER}")  # Debug print

def save_expense_document(file, expense_id):
    """Save uploaded document and return file info"""
    if file and file.filename:
        # Create secure filename with expense ID prefix
        filename = secure_filename(file.filename)
        # Add timestamp to prevent overwrites
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        unique_filename = f"expense_{expense_id}_{timestamp}{ext}"
        
        # Use absolute path
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        print(f"Saving file to: {filepath}")  # Debug print
        
        file.save(filepath)
        
        # Verify file was saved
        if not os.path.exists(filepath):
            raise Exception(f"File was not saved to {filepath}")
        
        # Get file info
        file_size = os.path.getsize(filepath)
        
        return {
            'filename': filename,  # Original filename
            'path': filepath,  # Full absolute path
            'size': file_size,
            'type': file.content_type
        }
    return None

def delete_expense_document(expense):
    """Delete the expense document file"""
    if expense.document_path and os.path.exists(expense.document_path):
        try:
            os.remove(expense.document_path)
            print(f"Deleted file: {expense.document_path}")  # Debug print
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    return False

@bp.route('/')
@login_required
@manager_required
def list_expenses():
    """List all expenses with filtering and pagination"""
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)
    
    # Default date range (current month)
    if not start_date:
        start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Build query
    query = Expense.query
    
    # Date filter
    if start_date:
        query = query.filter(Expense.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Expense.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    
    # Category filter
    if category and category != 'all':
        query = query.filter(Expense.category == category)
    
    # Order by date (newest first)
    expenses = query.order_by(desc(Expense.date), desc(Expense.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Calculate summary statistics
    total_expenses = query.count()
    total_amount = db.session.query(func.sum(Expense.amount)).filter(
        query.whereclause if query.whereclause is not None else True
    ).scalar() or 0
    
    # Get expense categories for filter dropdown
    categories = Expense.CATEGORIES
    
    return render_template('expenses/list.html',
                         expenses=expenses,
                         start_date=start_date,
                         end_date=end_date,
                         category=category,
                         total_expenses=total_expenses,
                         total_amount=total_amount,
                         categories=categories)

@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    """Add a new expense with required supporting document"""
    form = ExpenseForm()
    
    if form.validate_on_submit():
        # Create expense first to get ID
        expense = Expense(
            category=form.category.data,
            description=form.description.data.strip(),
            amount=form.amount.data,
            date=form.date.data,
            user_id=current_user.id,
            receipt_number=form.receipt_number.data.strip() if form.receipt_number.data else None,
            notes=form.notes.data.strip() if form.notes.data else None
        )
        
        db.session.add(expense)
        db.session.flush()  # Get expense ID before committing
        
        # Handle file upload
        file = form.supporting_document.data
        if file:
            # Validate file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > Expense.MAX_FILE_SIZE:
                flash(f'File size exceeds maximum allowed size of {Expense.MAX_FILE_SIZE / (1024*1024)}MB', 'error')
                db.session.rollback()
                return render_template('expenses/edit.html', form=form, title='Add Expense')
            
            # Save file
            try:
                file_info = save_expense_document(file, expense.id)
                if file_info:
                    expense.document_filename = file_info['filename']
                    expense.document_path = file_info['path']
                    expense.document_size = file_info['size']
                    expense.document_type = file_info['type']
                else:
                    flash('Error uploading file. Please try again.', 'error')
                    db.session.rollback()
                    return render_template('expenses/edit.html', form=form, title='Add Expense')
            except Exception as e:
                flash(f'Error uploading file: {str(e)}', 'error')
                db.session.rollback()
                return render_template('expenses/edit.html', form=form, title='Add Expense')
        
        db.session.commit()
        
        flash(f'Expense "{expense.description}" of GHS {expense.amount:.2f} added successfully with supporting document!', 'success')
        return redirect(url_for('expenses.list_expenses'))
    
    return render_template('expenses/edit.html', form=form, title='Add Expense')

@bp.route('/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit_expense(expense_id):
    """Edit an existing expense"""
    expense = Expense.query.get_or_404(expense_id)
    form = ExpenseEditForm(obj=expense)
    
    if form.validate_on_submit():
        expense.category = form.category.data
        expense.description = form.description.data.strip()
        expense.amount = form.amount.data
        expense.date = form.date.data
        expense.receipt_number = form.receipt_number.data.strip() if form.receipt_number.data else None
        expense.notes = form.notes.data.strip() if form.notes.data else None
        
        # Handle new file upload (optional for editing)
        file = form.supporting_document.data
        if file:
            # Validate file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > Expense.MAX_FILE_SIZE:
                flash(f'File size exceeds maximum allowed size of {Expense.MAX_FILE_SIZE / (1024*1024)}MB', 'error')
                return render_template('expenses/edit.html', form=form, title='Edit Expense', expense=expense)
            
            # Delete old file
            delete_expense_document(expense)
            
            # Save new file
            try:
                file_info = save_expense_document(file, expense.id)
                if file_info:
                    expense.document_filename = file_info['filename']
                    expense.document_path = file_info['path']
                    expense.document_size = file_info['size']
                    expense.document_type = file_info['type']
            except Exception as e:
                flash(f'Error uploading file: {str(e)}', 'error')
                return render_template('expenses/edit.html', form=form, title='Edit Expense', expense=expense)
        
        db.session.commit()
        flash(f'Expense "{expense.description}" updated successfully!', 'success')
        return redirect(url_for('expenses.list_expenses'))
    
    return render_template('expenses/edit.html', form=form, title='Edit Expense', expense=expense)

@bp.route('/<int:expense_id>/delete', methods=['POST'])
@login_required
@manager_required
def delete_expense(expense_id):
    """Delete an expense and its document"""
    expense = Expense.query.get_or_404(expense_id)
    
    description = expense.description
    amount = expense.amount
    
    # Delete the file first
    delete_expense_document(expense)
    
    db.session.delete(expense)
    db.session.commit()
    
    flash(f'Expense "{description}" (GHS {amount:.2f}) and its supporting document deleted successfully!', 'info')
    return redirect(url_for('expenses.list_expenses'))

@bp.route('/<int:expense_id>/delete/confirm')
@login_required
@manager_required
def confirm_delete_expense(expense_id):
    """Show confirmation page before deleting expense"""
    expense = Expense.query.get_or_404(expense_id)
    return render_template('expenses/confirm_delete.html', expense=expense)

@bp.route('/<int:expense_id>/download-document')
@login_required
def download_expense_document(expense_id):
    """Download the expense supporting document"""
    expense = Expense.query.get_or_404(expense_id)
    
    # Check permissions - only managers or the user who created it
    if not current_user.is_manager() and expense.user_id != current_user.id:
        flash('You do not have permission to access this document.', 'error')
        return redirect(url_for('expenses.list_expenses'))
    
    if not expense.has_document:
        flash('No document attached to this expense.', 'error')
        return redirect(url_for('expenses.list_expenses'))
    
    # Debug print
    print(f"Attempting to download: {expense.document_path}")
    print(f"File exists: {os.path.exists(expense.document_path)}")
    
    if not os.path.exists(expense.document_path):
        flash('Document file not found on server.', 'error')
        return redirect(url_for('expenses.list_expenses'))
    
    try:
        return send_file(
            expense.document_path,
            as_attachment=True,
            download_name=expense.document_filename
        )
    except Exception as e:
        print(f"Error sending file: {e}")
        flash(f'Error downloading document: {str(e)}', 'error')
        return redirect(url_for('expenses.list_expenses'))

@bp.route('/summary')
@login_required
def expense_summary():
    # Get date range from query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Convert string dates to datetime objects for calculation
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    days_in_period = (end_date_obj - start_date_obj).days + 1
    
    # Aggregate expenses by category
    category_data_raw = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total_amount')
    ).filter(
        Expense.date >= start_date_obj.date(),
        Expense.date <= end_date_obj.date()
    ).group_by(Expense.category).all()

    # Convert to list of dicts
    category_data = [
        {"category": row.category, "total_amount": float(row.total_amount)}
        for row in category_data_raw
    ]
    
    # Aggregate daily expenses
    daily_data_raw = db.session.query(
        Expense.date,
        func.sum(Expense.amount).label('total_amount')
    ).filter(
        Expense.date >= start_date_obj.date(),
        Expense.date <= end_date_obj.date()
    ).group_by(Expense.date).order_by(Expense.date).all()

    # Convert to list of dicts
    daily_data = [
        {"date": row.date.strftime("%Y-%m-%d"), "total_amount": float(row.total_amount)}
        for row in daily_data_raw
    ]
    
    # Calculate totals
    total_expenses = sum(item["total_amount"] for item in category_data) if category_data else 0
    daily_average = total_expenses / days_in_period if total_expenses > 0 and days_in_period > 0 else 0
    
    return render_template(
        'expenses/summary.html',
        start_date=start_date,
        end_date=end_date,
        total_expenses=total_expenses,
        daily_average=daily_average,
        days_in_period=days_in_period,
        category_data=category_data,
        daily_data=daily_data
    )