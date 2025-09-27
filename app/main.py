from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from datetime import datetime, date
from sqlalchemy import func, text
from app.models import Product, Sale, User
from app import db

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def index():
    current_date = datetime.now().strftime('%B %d, %Y')
    
    # Basic stats
    total_products = Product.query.count()
    low_stock_products = Product.query.filter(Product.quantity <= 5).count()
    
    # Today's sales count (only completed sales)
    today = date.today()
    total_sales_today = Sale.query.filter(
        func.date(Sale.created_at) == today,
        Sale.status == 'completed'
    ).count()
    
    # Recent sales with pagination
    page = request.args.get('page', 1, type=int)
    recent_sales = Sale.query.filter(
        Sale.status == 'completed'
    ).order_by(Sale.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # Low stock products list (first 10)
    low_stock_list = Product.query.filter(
        Product.quantity <= 5
    ).order_by(Product.quantity.asc()).limit(10).all()
    
    # User count (admin only)
    total_users = 0
    if current_user.is_admin():
        total_users = User.query.count()
    
    # Initialize stock values and stats
    stock_values = {
        'total_cost_value': 0,
        'total_retail_value': 0,
        'total_potential_profit': 0
    }
    
    stock_stats = {
        'total_products': 0,
        'in_stock_count': 0,
        'low_stock_count': 0,
        'out_of_stock_count': 0,
        'total_quantity': 0
    }
    
    # Calculate stock values for managers and admins
    if current_user.role in ['manager', 'admin']:
        try:
            # Stock value calculation
            stock_value_query = db.session.execute(text("""
                SELECT 
                    COALESCE(SUM(purchase_price * quantity), 0) as total_cost_value,
                    COALESCE(SUM(full_price * quantity), 0) as total_retail_value,
                    COALESCE(SUM(quantity), 0) as total_quantity
                FROM product
            """)).fetchone()
            
            if stock_value_query:
                stock_values['total_cost_value'] = float(stock_value_query.total_cost_value or 0)
                stock_values['total_retail_value'] = float(stock_value_query.total_retail_value or 0)
                stock_values['total_potential_profit'] = stock_values['total_retail_value'] - stock_values['total_cost_value']
            
            # Stock statistics
            stock_stats_query = db.session.execute(text("""
                SELECT 
                    COUNT(*) as total_products,
                    SUM(CASE WHEN quantity > 0 THEN 1 ELSE 0 END) as in_stock_count,
                    SUM(CASE WHEN quantity > 0 AND quantity <= 5 THEN 1 ELSE 0 END) as low_stock_count,
                    SUM(CASE WHEN quantity = 0 THEN 1 ELSE 0 END) as out_of_stock_count,
                    COALESCE(SUM(quantity), 0) as total_quantity
                FROM product
            """)).fetchone()
            
            if stock_stats_query:
                stock_stats['total_products'] = int(stock_stats_query.total_products or 0)
                stock_stats['in_stock_count'] = int(stock_stats_query.in_stock_count or 0)
                stock_stats['low_stock_count'] = int(stock_stats_query.low_stock_count or 0)
                stock_stats['out_of_stock_count'] = int(stock_stats_query.out_of_stock_count or 0)
                stock_stats['total_quantity'] = int(stock_stats_query.total_quantity or 0)
                
        except Exception as e:
            # Log error but continue with default values
            print(f"Error calculating stock values: {e}")
    
    return render_template('index.html',
                         current_date=current_date,
                         total_products=total_products,
                         low_stock_products=low_stock_products,
                         total_sales_today=total_sales_today,
                         total_users=total_users,
                         recent_sales=recent_sales,
                         low_stock_list=low_stock_list,
                         stock_values=stock_values,
                         stock_stats=stock_stats)