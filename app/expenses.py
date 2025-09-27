from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import Expense
from app.forms import ExpenseForm
from app.decorators import manager_required
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc

bp = Blueprint('expenses', __name__)

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
#@manager_required
def add_expense():
    """Add a new expense"""
    form = ExpenseForm()
    
    if form.validate_on_submit():
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
        db.session.commit()
        
        flash(f'Expense "{expense.description}" of GHS {expense.amount:.2f} added successfully!', 'success')
        return redirect(url_for('expenses.list_expenses'))
    
    return render_template('expenses/edit.html', form=form, title='Add Expense')

@bp.route('/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit_expense(expense_id):
    """Edit an existing expense"""
    expense = Expense.query.get_or_404(expense_id)
    form = ExpenseForm(obj=expense)
    
    if form.validate_on_submit():
        expense.category = form.category.data
        expense.description = form.description.data.strip()
        expense.amount = form.amount.data
        expense.date = form.date.data
        expense.receipt_number = form.receipt_number.data.strip() if form.receipt_number.data else None
        expense.notes = form.notes.data.strip() if form.notes.data else None
        
        db.session.commit()
        flash(f'Expense "{expense.description}" updated successfully!', 'success')
        return redirect(url_for('expenses.list_expenses'))
    
    return render_template('expenses/edit.html', form=form, title='Edit Expense', expense=expense)

@bp.route('/<int:expense_id>/delete', methods=['POST'])
@login_required
@manager_required
def delete_expense(expense_id):
    """Delete an expense"""
    expense = Expense.query.get_or_404(expense_id)
    
    description = expense.description
    amount = expense.amount
    
    db.session.delete(expense)
    db.session.commit()
    
    flash(f'Expense "{description}" (GHS {amount:.2f}) deleted successfully!', 'info')
    return redirect(url_for('expenses.list_expenses'))

@bp.route('/<int:expense_id>/delete/confirm')
@login_required
@manager_required
def confirm_delete_expense(expense_id):
    """Show confirmation page before deleting expense"""
    expense = Expense.query.get_or_404(expense_id)
    return render_template('expenses/confirm_delete.html', expense=expense)

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
