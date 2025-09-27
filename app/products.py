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
    page = request.args.get('page', 1, type=int)
    
    query = Product.query
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.description.ilike(search_term)
            )
        )
    
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
    
    return render_template('products/list.html', 
                         products=products, 
                         search=search,
                         total_stock_value=total_stock_value,
                         total_retail_value=total_retail_value,
                         potential_profit=potential_profit,
                         total_products=total_products,
                         low_stock_count=low_stock_count,
                         out_of_stock_count=out_of_stock_count)

@bp.route('/add', methods=['GET', 'POST'])
@login_required
@manager_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(
            sku=form.sku.data.strip(),
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else '',
            purchase_price=form.purchase_price.data,
            full_price=form.full_price.data,
            price=form.full_price.data,  # For backward compatibility
            quantity=form.quantity.data
        )
        db.session.add(product)
        db.session.commit()
        flash(f'Product {product.name} added successfully!', 'success')
        return redirect(url_for('products.list_products'))
    
    return render_template('products/edit.html', form=form, title='Add Product')

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
                    # Validate required fields
                    if not all([row.get('sku'), row.get('name'), row.get('purchase_price'), row.get('full_price')]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Check if SKU already exists
                    if Product.query.filter_by(sku=row['sku'].strip()).first():
                        errors.append(f"Row {row_num}: SKU '{row['sku']}' already exists")
                        continue
                    
                    # Create product
                    product = Product(
                        sku=row['sku'].strip(),
                        name=row['name'].strip(),
                        description=row.get('description', '').strip(),
                        purchase_price=Decimal(str(row['purchase_price'])),
                        full_price=Decimal(str(row['full_price'])),
                        price=Decimal(str(row['full_price'])),
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
                flash(f'Successfully added {added_count} products', 'success')
            
            if errors:
                flash(f'Errors: {"; ".join(errors[:5])}{"..." if len(errors) > 5 else ""}', 'warning')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'error')
    
    return render_template('products/bulk_add.html')

@bp.route('/bulk-update', methods=['POST'])
@login_required
@manager_required
def bulk_update_products():
    """Bulk update product quantities and prices"""
    try:
        updates = request.json.get('updates', [])
        if not updates:
            return jsonify({'success': False, 'error': 'No updates provided'})
        
        updated_count = 0
        errors = []
        
        for update in updates:
            try:
                product_id = int(update.get('id'))
                product = Product.query.get(product_id)
                
                if not product:
                    errors.append(f'Product ID {product_id} not found')
                    continue
                
                # Update fields if provided
                if 'quantity' in update:
                    product.quantity = int(update['quantity'])
                
                if 'purchase_price' in update:
                    product.purchase_price = Decimal(str(update['purchase_price']))
                
                if 'full_price' in update:
                    product.full_price = Decimal(str(update['full_price']))
                    product.price = product.full_price  # Keep backward compatibility
                
                updated_count += 1
                
            except (ValueError, TypeError) as e:
                errors.append(f'Invalid data for product {update.get("id", "unknown")}: {str(e)}')
            except Exception as e:
                errors.append(f'Error updating product {update.get("id", "unknown")}: {str(e)}')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/bulk-delete', methods=['POST'])
@login_required
@admin_required
def bulk_delete_products():
    """Bulk delete selected products"""
    try:
        product_ids = request.json.get('product_ids', [])
        if not product_ids:
            return jsonify({'success': False, 'error': 'No products selected'})
        
        # Get products and check if they have sales history
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        
        cannot_delete = []
        can_delete = []
        
        for product in products:
            if product.sale_items:
                cannot_delete.append(product.name)
            else:
                can_delete.append(product)
        
        # Delete products that can be deleted
        deleted_count = 0
        for product in can_delete:
            db.session.delete(product)
            deleted_count += 1
        
        db.session.commit()
        
        message = f'Deleted {deleted_count} products'
        if cannot_delete:
            message += f'. Could not delete {len(cannot_delete)} products with sales history: {", ".join(cannot_delete[:3])}'
            if len(cannot_delete) > 3:
                message += '...'
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'cannot_delete_count': len(cannot_delete),
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    form = ProductForm(original_sku=product.sku, obj=product)
    
    if form.validate_on_submit():
        product.sku = form.sku.data.strip()
        product.name = form.name.data.strip()
        product.description = form.description.data.strip() if form.description.data else ''
        product.purchase_price = form.purchase_price.data
        product.full_price = form.full_price.data
        product.price = form.full_price.data  # For backward compatibility
        product.quantity = form.quantity.data
        db.session.commit()
        flash(f'Product {product.name} updated successfully!', 'success')
        return redirect(url_for('products.list_products'))
    
    return render_template('products/edit.html', form=form, title='Edit Product', product=product)

@bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Check if product has sales history
    if product.sale_items:
        flash('Cannot delete product with existing sales history.', 'danger')
        return redirect(url_for('products.list_products'))
    
    product_name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f'Product {product_name} deleted successfully!', 'info')
    return redirect(url_for('products.list_products'))

@bp.route('/search')
@login_required
def search_products():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    products = Product.query.filter(
        Product.name.ilike(f'%{q}%') |
        Product.sku.ilike(f'%{q}%')
    ).all()

    results = [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
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
    products = Product.query.all()
    results = [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
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

@bp.route('/download-template')
@login_required
@manager_required
def download_csv_template():
    """Download CSV template for bulk upload"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['sku', 'name', 'description', 'purchase_price', 'full_price', 'quantity'])
    
    # Write sample data
    writer.writerow(['SAMPLE001', 'Sample Product 1', 'Sample description', '10.00', '15.00', '100'])
    writer.writerow(['SAMPLE002', 'Sample Product 2', 'Another description', '5.50', '8.25', '50'])
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=products_template.csv'
    
    return response