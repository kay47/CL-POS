# Update your products.py routes

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_required, current_user
from app.models import Product
from app.forms import ProductForm
from app.decorators import admin_required, manager_required
from app import db
from sqlalchemy import or_, func
from decimal import Decimal
import csv
import io

bp = Blueprint('products', __name__)

@bp.route('/')
@login_required
@manager_required
def list_products():
    search = request.args.get('q', '').strip()
    category_filter = request.args.get('category', 'all')
    page = request.args.get('page', 1, type=int)
    
    query = Product.query
    
    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.description.ilike(search_term)
            )
        )
    
    # Category filter
    if category_filter and category_filter != 'all':
        query = query.filter(Product.category == category_filter)
    
    products = query.order_by(Product.name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Calculate stock values
    total_stock_value = db.session.query(
        func.sum(Product.purchase_price * Product.quantity)
    ).scalar() or 0
    
    total_retail_value = db.session.query(
        func.sum(Product.full_price * Product.quantity)
    ).scalar() or 0
    
    potential_profit = float(total_retail_value) - float(total_stock_value)
    
    # Stock statistics
    total_products = Product.query.count()
    low_stock_count = Product.query.filter(Product.quantity <= 5).count()
    out_of_stock_count = Product.query.filter(Product.quantity == 0).count()
    
    # Category statistics
    category_stats = db.session.query(
        Product.category,
        func.count(Product.id).label('count'),
        func.sum(Product.quantity).label('total_quantity'),
        func.sum(Product.purchase_price * Product.quantity).label('total_value')
    ).group_by(Product.category).all()
    
    return render_template('products/list.html', 
                         products=products, 
                         search=search,
                         category_filter=category_filter,
                         categories=Product.CATEGORIES,
                         total_stock_value=total_stock_value,
                         total_retail_value=total_retail_value,
                         potential_profit=potential_profit,
                         total_products=total_products,
                         low_stock_count=low_stock_count,
                         out_of_stock_count=out_of_stock_count,
                         category_stats=category_stats)

# Update the add_product and edit_product functions in products.py

@bp.route('/add', methods=['GET', 'POST'])
@login_required
@manager_required
def add_product():
    form = ProductForm()
    
    # For new products, we don't need SKU in the form
    if request.method == 'GET':
        form.sku.data = '[Auto-generated]'  # Show this in the form
    
    if form.validate_on_submit():
        try:
            # Auto-calculate half_price if not provided
            half_price = form.half_price.data
            if not half_price and form.full_price.data:
                half_price = form.full_price.data / 2
            
            # Create product with auto-generated SKU
            product = Product.create_with_auto_sku(
                name=form.name.data.strip(),
                category=form.category.data,
                description=form.description.data.strip() if form.description.data else '',
                purchase_price=form.purchase_price.data,
                full_price=form.full_price.data,
                half_price=half_price,
                quantity=form.quantity.data
            )
            
            db.session.add(product)
            db.session.commit()
            
            flash(f'Product "{product.name}" added successfully with SKU: {product.sku}!', 'success')
            return redirect(url_for('products.list_products'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating product: {str(e)}', 'error')
    
    return render_template('products/edit.html', form=form, title='Add Product')

@bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    form = ProductForm(original_sku=product.sku, obj=product)
    
    if form.validate_on_submit():
        try:
            # Check if category changed - if so, generate new SKU
            if form.category.data != product.category:
                new_sku = Product.generate_sku(form.category.data)
                
                # Ensure uniqueness
                counter = 1
                original_sku = new_sku
                while Product.query.filter_by(sku=new_sku).filter(Product.id != product.id).first():
                    base = original_sku[:3]
                    base_number = int(original_sku[3:])
                    new_sku = f"{base}{(base_number + counter):04d}"
                    counter += 1
                
                product.sku = new_sku
                flash(f'Category changed - New SKU generated: {new_sku}', 'info')
            
            # Update other fields
            product.name = form.name.data.strip()
            product.category = form.category.data
            product.description = form.description.data.strip() if form.description.data else ''
            product.purchase_price = form.purchase_price.data
            product.full_price = form.full_price.data
            product.half_price = form.half_price.data if form.half_price.data else product.full_price / 2
            product.price = form.full_price.data  # For backward compatibility
            product.quantity = form.quantity.data
            
            db.session.commit()
            flash(f'Product "{product.name}" updated successfully!', 'success')
            return redirect(url_for('products.list_products'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'error')
    
    return render_template('products/edit.html', form=form, title='Edit Product', product=product)

@bp.route('/bulk-add', methods=['GET', 'POST'])
@login_required
@manager_required
def bulk_add_products():
    """Bulk add products via CSV upload"""
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if not file.filename.lower().endswith('.csv'):
            flash('Please upload a CSV file', 'error')
            return redirect(request.url)
        
        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            added_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Validate required fields (no SKU needed)
                    if not all([row.get('name'), row.get('category'), row.get('purchase_price'), row.get('full_price')]):
                        errors.append(f"Row {row_num}: Missing required fields (name, category, purchase_price, full_price)")
                        continue
                    
                    # Validate category
                    valid_categories = [cat[0] for cat in Product.CATEGORIES]
                    if row['category'] not in valid_categories:
                        errors.append(f"Row {row_num}: Invalid category '{row['category']}'. Valid options: {', '.join(valid_categories)}")
                        continue
                    
                    # Create product with auto-generated SKU
                    product = Product.create_with_auto_sku(
                        name=row['name'].strip(),
                        category=row['category'],
                        description=row.get('description', '').strip(),
                        purchase_price=Decimal(str(row['purchase_price'])),
                        full_price=Decimal(str(row['full_price'])),
                        quantity=int(row.get('quantity', 0))
                    )
                    
                    db.session.add(product)
                    added_count += 1
                    
                except ValueError as e:
                    errors.append(f"Row {row_num}: Invalid data format - {str(e)}")
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            db.session.commit()
            
            if added_count > 0:
                flash(f'Successfully added {added_count} products with auto-generated SKUs', 'success')
            
            if errors:
                flash(f'Errors: {"; ".join(errors[:5])}{"..." if len(errors) > 5 else ""}', 'warning')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'error')
    
    return render_template('products/bulk_add.html')

@bp.route('/download-template')
@login_required
@manager_required
def download_csv_template():
    """Download CSV template for bulk upload"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header (no SKU field)
    writer.writerow(['name', 'category', 'description', 'purchase_price', 'full_price', 'quantity'])
    
    # Write sample data with valid categories
    writer.writerow(['Sample Electronics Item', 'electronics', 'Sample description', '10.00', '15.00', '100'])
    writer.writerow(['Sample Clothing Item', 'clothing', 'Another description', '5.50', '8.25', '50'])
    writer.writerow(['Sample Food Item', 'food', 'Food item description', '2.00', '3.50', '200'])
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=products_template.csv'
    
    return response

# Keep other existing routes unchanged
@bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if product.sale_items:
        flash('Cannot delete product with existing sales history.', 'danger')
        return redirect(url_for('products.list_products'))
    
    product_name = product.name
    product_sku = product.sku
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{product_name}" (SKU: {product_sku}) deleted successfully!', 'info')
    return redirect(url_for('products.list_products'))

@bp.route('/search')
@login_required
def search_products():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    
    if not q and not category:
        return jsonify([])

    query = Product.query
    
    if q:
        search_term = f'%{q}%'
        query = query.filter(
            Product.name.ilike(search_term) |
            Product.sku.ilike(search_term)
        )
    
    if category and category != 'all':
        query = query.filter(Product.category == category)

    products = query.all()

    results = [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category_display,
            "price": float(p.full_price),
            "stock": float(p.quantity),
            "status": (
                "Out of Stock" if p.quantity == 0 
                else "Low Stock" if p.quantity <= 5 
                else "In Stock"
            )
        }
        for p in products
    ]
    return jsonify(results)

@bp.route('/all')
@login_required
def all_products():
    category = request.args.get('category', '')
    
    query = Product.query
    if category and category != 'all':
        query = query.filter(Product.category == category)
    
    products = query.all()
    results = [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category_display,
            "price": float(p.full_price),
            "quantity": float(p.quantity),
            "status": (
                "Out of Stock" if p.quantity == 0
                else "Low Stock" if p.quantity <= 5
                else "In Stock"
            )
        }
        for p in products
    ]
    return jsonify(results)