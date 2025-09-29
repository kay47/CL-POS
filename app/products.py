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
    writer.writerow(['Sample beauty Item', 'beauty', 'beauty item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample books Item', 'books', 'books item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample home Item', 'home', 'home item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample sports Item', 'sports', 'sports item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample automotive Item', 'automotive', 'automotive item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample toys Item', 'toys', 'toys item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample health Item', 'health', 'health item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample jewelry Item', 'jewelry', 'jewelry item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample music Item', 'music', 'music item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample pets Item', 'pets', 'pets item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample office Item', 'office', 'office item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample tools Item', 'tools', 'tools item description', '2.00', '3.50', '200'])
    writer.writerow(['Sample other Item', 'other', 'other item description', '2.00', '3.50', '200'])
    
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

@bp.route('/bulk-update', methods=['POST'])
@login_required
@admin_required
def bulk_update_products():
    """Handle bulk update of products"""
    print("=== BULK UPDATE DEBUG START ===")
    
    try:
        # Check if request has JSON content
        if not request.is_json:
            print(f"ERROR: Request is not JSON. Content-Type: {request.content_type}")
            return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
        
        data = request.get_json()
        print(f"Received data: {data}")
        
        if not data:
            print("ERROR: No data provided")
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        product_ids = data.get('product_ids', [])
        print(f"Product IDs: {product_ids}")
        
        if not product_ids:
            print("ERROR: No products selected")
            return jsonify({'success': False, 'message': 'No products selected'}), 400
        
        # Convert string IDs to integers
        try:
            product_ids = [int(pid) for pid in product_ids]
            print(f"Converted product IDs: {product_ids}")
        except (ValueError, TypeError) as e:
            print(f"ERROR: Invalid product ID format: {e}")
            return jsonify({'success': False, 'message': f'Invalid product ID format: {str(e)}'}), 400
        
        # Get the products to update
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        print(f"Found {len(products)} products to update")
        
        if not products:
            print("ERROR: No valid products found")
            return jsonify({'success': False, 'message': 'No valid products found'}), 404
        
        updated_count = 0
        
        for product in products:
            print(f"Updating product: {product.sku} - {product.name}")
            
            try:
                # Update purchase price
                if data.get('purchase_price') is not None and str(data['purchase_price']).strip() != '':
                    try:
                        new_purchase_price = Decimal(str(data['purchase_price']))
                        print(f"  Setting purchase price: {new_purchase_price}")
                        if new_purchase_price >= 0:
                            product.purchase_price = new_purchase_price
                    except (ValueError, TypeError) as e:
                        error_msg = f'Invalid purchase price format for product {product.sku}: {str(e)}'
                        print(f"ERROR: {error_msg}")
                        return jsonify({'success': False, 'message': error_msg}), 400
                
                # Update full price
                if data.get('full_price') is not None and str(data['full_price']).strip() != '':
                    try:
                        new_full_price = Decimal(str(data['full_price']))
                        print(f"  Setting full price: {new_full_price}")
                        if new_full_price > 0:
                            product.full_price = new_full_price
                            product.price = new_full_price  # For backward compatibility
                    except (ValueError, TypeError) as e:
                        error_msg = f'Invalid full price format for product {product.sku}: {str(e)}'
                        print(f"ERROR: {error_msg}")
                        return jsonify({'success': False, 'message': error_msg}), 400
                
                # Update half price or auto-calculate
                if data.get('half_price') is not None and str(data['half_price']).strip() != '':
                    try:
                        new_half_price = Decimal(str(data['half_price']))
                        print(f"  Setting half price: {new_half_price}")
                        if new_half_price > 0:
                            product.half_price = new_half_price
                    except (ValueError, TypeError) as e:
                        error_msg = f'Invalid half price format for product {product.sku}: {str(e)}'
                        print(f"ERROR: {error_msg}")
                        return jsonify({'success': False, 'message': error_msg}), 400
                elif data.get('full_price') is not None and str(data['full_price']).strip() != '':
                    # Auto-calculate half price if full price was updated but half price not provided
                    auto_half_price = product.full_price / Decimal('2')
                    print(f"  Auto-calculating half price: {auto_half_price}")
                    product.half_price = auto_half_price
                
                # Update quantity
                if data.get('quantity') is not None and str(data['quantity']).strip() != '':
                    try:
                        new_quantity = int(data['quantity'])
                        print(f"  Setting quantity: {new_quantity}")
                        if new_quantity >= 0:
                            product.quantity = new_quantity
                    except (ValueError, TypeError) as e:
                        error_msg = f'Invalid quantity format for product {product.sku}: {str(e)}'
                        print(f"ERROR: {error_msg}")
                        return jsonify({'success': False, 'message': error_msg}), 400
                
                # Update category
                if data.get('category') is not None and str(data['category']).strip() != '':
                    new_category = str(data['category']).strip()
                    print(f"  Setting category: {new_category}")
                    
                    # Validate category
                    valid_categories = [cat[0] for cat in Product.CATEGORIES]
                    print(f"  Valid categories: {valid_categories}")
                    
                    if new_category in valid_categories:
                        old_category = product.category
                        product.category = new_category
                        
                        # If category changed, generate new SKU
                        if old_category != new_category:
                            try:
                                print(f"  Category changed from {old_category} to {new_category}, generating new SKU")
                                new_sku = Product.generate_sku(new_category)
                                
                                # Ensure uniqueness
                                counter = 1
                                original_sku = new_sku
                                while Product.query.filter_by(sku=new_sku).filter(Product.id != product.id).first():
                                    base = original_sku[:3]
                                    base_number = int(original_sku[3:])
                                    new_sku = f"{base}{(base_number + counter):04d}"
                                    counter += 1
                                
                                print(f"  Generated new SKU: {new_sku}")
                                product.sku = new_sku
                            except Exception as sku_error:
                                error_msg = f'Error generating SKU for product {product.sku}: {str(sku_error)}'
                                print(f"ERROR: {error_msg}")
                                return jsonify({'success': False, 'message': error_msg}), 400
                    else:
                        error_msg = f'Invalid category "{new_category}" for product {product.sku}. Valid options: {", ".join(valid_categories)}'
                        print(f"ERROR: {error_msg}")
                        return jsonify({'success': False, 'message': error_msg}), 400
                
                # Validate prices after all updates
                print(f"  Validating prices - Purchase: {product.purchase_price}, Full: {product.full_price}, Half: {product.half_price}")
                
                if product.purchase_price >= product.full_price:
                    error_msg = f'Purchase price (GHS {product.purchase_price}) must be less than full price (GHS {product.full_price}) for product {product.sku}'
                    print(f"ERROR: {error_msg}")
                    return jsonify({'success': False, 'message': error_msg}), 400
                
                if product.half_price and product.half_price >= product.full_price:
                    error_msg = f'Half price (GHS {product.half_price}) must be less than full price (GHS {product.full_price}) for product {product.sku}'
                    print(f"ERROR: {error_msg}")
                    return jsonify({'success': False, 'message': error_msg}), 400
                
                updated_count += 1
                print(f"  Successfully updated product {product.sku}")
                
            except Exception as product_error:
                error_msg = f'Error updating product {product.sku}: {str(product_error)}'
                print(f"ERROR: {error_msg}")
                return jsonify({'success': False, 'message': error_msg}), 400
        
        # Commit all changes
        try:
            print(f"Committing changes for {updated_count} products")
            db.session.commit()
            print("Database commit successful")
        except Exception as commit_error:
            db.session.rollback()
            error_msg = f'Database error while saving changes: {str(commit_error)}'
            print(f"ERROR: {error_msg}")
            return jsonify({'success': False, 'message': error_msg}), 500
        
        success_msg = f'Successfully updated {updated_count} products'
        print(f"SUCCESS: {success_msg}")
        print("=== BULK UPDATE DEBUG END ===")
        
        return jsonify({
            'success': True, 
            'message': success_msg,
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Unexpected error: {str(e)}'
        print(f"FATAL ERROR: {error_msg}")
        print("=== BULK UPDATE DEBUG END (WITH ERROR) ===")
        return jsonify({'success': False, 'message': error_msg}), 500
    
    # Add this route to your products.py file

@bp.route('/bulk-delete', methods=['POST'])
@login_required
@admin_required
def bulk_delete_products():
    """Handle bulk deletion of products"""
    try:
        product_ids = request.form.getlist('product_ids[]')
        
        if not product_ids:
            flash('No products selected for deletion.', 'error')
            return redirect(url_for('products.list_products'))
        
        # Convert to integers
        try:
            product_ids = [int(pid) for pid in product_ids]
        except ValueError:
            flash('Invalid product IDs provided.', 'error')
            return redirect(url_for('products.list_products'))
        
        # Get the products to delete
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        
        if not products:
            flash('No valid products found for deletion.', 'error')
            return redirect(url_for('products.list_products'))
        
        # Check if any products have sales history
        products_with_sales = []
        products_to_delete = []
        
        for product in products:
            if product.sale_items:
                products_with_sales.append(product)
            else:
                products_to_delete.append(product)
        
        # If some products have sales history, show error
        if products_with_sales:
            product_names = [p.name for p in products_with_sales[:3]]
            more_count = len(products_with_sales) - 3
            names_str = ', '.join(product_names)
            if more_count > 0:
                names_str += f' and {more_count} more'
            
            flash(f'Cannot delete products with sales history: {names_str}', 'error')
            
            # If no products can be deleted, return early
            if not products_to_delete:
                return redirect(url_for('products.list_products'))
        
        # Delete the products that don't have sales history
        deleted_count = 0
        deleted_names = []
        
        for product in products_to_delete:
            deleted_names.append(f"{product.name} ({product.sku})")
            db.session.delete(product)
            deleted_count += 1
        
        db.session.commit()
        
        if deleted_count > 0:
            if deleted_count <= 3:
                flash(f'Successfully deleted: {", ".join(deleted_names)}', 'success')
            else:
                flash(f'Successfully deleted {deleted_count} products', 'success')
        
        return redirect(url_for('products.list_products'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting products: {str(e)}', 'error')
        return redirect(url_for('products.list_products'))