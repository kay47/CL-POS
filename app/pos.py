from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, current_app, session
from flask_login import login_required, current_user
from app.models import Product, Sale, SaleItem
from app.decorators import manager_required, role_required
from app import db
from decimal import Decimal
from app.forms import SaleStatusForm
from datetime import datetime
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from sqlalchemy import text  # Add this import at the top of pos.py


bp = Blueprint('pos', __name__)

@bp.route('/')
@login_required
def pos_page():
    products = Product.query.filter(Product.quantity > 0).order_by(Product.name).all()

    # Check if we're continuing a sale
    continue_sale_id = session.get('continue_sale_id')
    if continue_sale_id:
        session.pop('continue_sale_id', None)  # Remove from session after use
        return render_template('pos/pos.html', products=products, continue_sale_id=continue_sale_id)
    
    return render_template('pos/pos.html', products=products)

@bp.route('/preview', methods=['POST'])
@login_required
def checkout_preview():
    """Show preview of items before completing the sale"""
    try:
        items = request.json.get('items', [])
        if not items:
            return jsonify({'error': 'No items in cart'}), 400
        
        # Validate items and calculate totals
        preview_items = []
        total = Decimal('0.00')
        total_profit = Decimal('0.00')
        
        for item in items:
            product_id = int(item['product_id'])
            quantity = int(item['quantity'])
            unit_type = item.get('unit_type', 'full')
            
            product = Product.query.get(product_id)
            if not product:
                return jsonify({'error': f'Product not found'}), 400
            
            if product.quantity < quantity:
                return jsonify({'error': f'Insufficient stock for {product.name}. Available: {product.quantity}'}), 400
            
            # Get price based on unit type
            price = product.get_price_for_unit(unit_type)
            line_total = Decimal(str(price)) * quantity
            total += line_total
            
            # Calculate profit for this line
            line_profit = Decimal(str(product.get_profit_for_unit(unit_type))) * quantity
            total_profit += line_profit
            
            preview_items.append({
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku,
                'unit_type': unit_type,
                'price': float(price),
                'quantity': quantity,
                'line_total': float(line_total),
                'line_profit': float(line_profit),
                'available_stock': product.quantity
            })
        
        return jsonify({
            'success': True,
            'items': preview_items,
            'total': float(total),
            'total_profit': float(total_profit),
            'item_count': len(preview_items)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    """Complete the sale with fractional pricing and payment processing"""
    try:
        data = request.json
        items = data.get('items', [])
        sale_status = data.get('status', 'completed')
        payment_method = data.get('payment_method', 'cash')
        amount_paid = Decimal(str(data.get('amount_paid', 0)))
        change_given = Decimal(str(data.get('change_given', 0)))
        
        if not items:
            return jsonify({'error': 'No items in cart'}), 400
        
        # Validate status
        if sale_status not in ['completed', 'pending']:
            sale_status = 'completed'
            
        # Validate payment method
        if payment_method not in ['cash', 'card', 'mobile_money', 'bank_transfer']:
            payment_method = 'cash'

        # Get continuing sale id from session
        continuing_sale_id = session.get('continue_sale_id')

        # Handle continuing sale vs new sale
        if continuing_sale_id:
            # Update existing pending sale
            sale = Sale.query.get(continuing_sale_id)
            if not sale or sale.status != 'pending':
                return jsonify({'error': 'Invalid pending sale'}), 400
            
            # Check permissions
            if current_user.role == 'cashier' and sale.clerk_id != current_user.id:
                return jsonify({'error': 'Access denied'}), 403
            
            # Clear existing sale items and restore their inventory
            for item in sale.sale_items:
                item.product.quantity += item.quantity
                db.session.delete(item)
            
            # Update sale details
            sale.payment_method = payment_method
            sale.amount_paid = amount_paid
            sale.change_given = change_given
            sale.status = sale_status
            
            session.pop('continue_sale_id', None)
        else:
            # Create new sale
            sale = Sale(
                clerk_id=current_user.id, 
                total_amount=0,
                total_profit=Decimal('0.00'),
                status=sale_status,
                payment_method=payment_method,
                amount_paid=amount_paid,
                change_given=change_given
            )
            db.session.add(sale)
        
        db.session.flush()  # Get sale ID
        
        total = Decimal('0.00')
        total_profit = Decimal('0.00')
        
        for item in items:
            product_id = int(item['product_id'])
            quantity = int(item['quantity'])
            unit_type = item.get('unit_type', 'full')
            
            product = Product.query.get(product_id)
            if not product:
                raise ValueError(f'Product not found')
            
            if product.quantity < quantity:
                raise ValueError(f'Insufficient stock for {product.name}')
            
            # Get price and cost based on unit type
            price = product.get_price_for_unit(unit_type)
            
            # Calculate cost basis for profit tracking
            if unit_type == 'full':
                cost_basis = product.purchase_price
            elif unit_type == 'half':
                cost_basis = product.purchase_price / Decimal('2')
            elif unit_type == 'quarter':
                cost_basis = product.purchase_price / Decimal('4')
            else:
                cost_basis = product.purchase_price
            
            # Update stock only if sale is completed
            if sale_status == 'completed':
                product.quantity -= quantity
            
            # Create sale item with unit type and cost tracking
            sale_item = SaleItem(
                sale=sale,
                product=product,
                quantity=quantity,
                unit_type=unit_type,
                price_at_sale=price,
                cost_at_sale=cost_basis
            )
            db.session.add(sale_item)
            
            line_total = Decimal(str(price)) * quantity
            line_profit = (Decimal(str(price)) - Decimal(str(cost_basis))) * quantity
            
            total += line_total
            total_profit += line_profit
        
        # FIXED: Assign both totals
        sale.total_amount = float(total)
        sale.total_profit = float(total_profit)
        
        # Validate payment amount for completed sales
        if sale_status == 'completed' and amount_paid < total:
            raise ValueError('Payment amount is less than total amount')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'invoice_number': sale.invoice_number,
            'total': float(total),
            'total_profit': float(total_profit),
            'payment_method': payment_method,
            'amount_paid': float(amount_paid),
            'change_given': float(change_given),
            'status': sale.status,
            'message': f'Sale {sale.invoice_number} completed successfully!'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    

# Fix the sales list route (remove the broken one and keep this correct one)
"""@bp.route('/sales/list')
@login_required
@role_required(['clerk', 'manager', 'admin'])
def list_sales():
    Display list of sales with filtering and pagination
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    # Build query based on user role and status filter
    query = Sale.query
    
    # Regular clerks can only see their own sales
    if current_user.role == 'clerk':
        query = query.filter(Sale.clerk_id == current_user.id)
    
    # Apply status filter
    if status_filter != 'all':
        query = query.filter(Sale.status == status_filter)
    
    # Paginate results
    sales = query.order_by(Sale.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template(
        'pos/sales_list.html', 
        sales=sales, 
        status_filter=status_filter,
        current_time=datetime.now()
    )"""

@bp.route('/sales/<int:sale_id>/status', methods=['GET', 'POST'])
@login_required
@manager_required
def update_sale_status(sale_id):
    """Update sale status with inventory adjustments"""
    sale = Sale.query.get_or_404(sale_id)
    form = SaleStatusForm(obj=sale)
    
    if form.validate_on_submit():
        old_status = sale.status
        new_status = form.status.data
        
        # Handle inventory changes when status changes
        if old_status != new_status:
            if old_status == 'completed' and new_status in ['pending', 'cancelled']:
                # Return items to inventory
                for item in sale.sale_items:
                    item.product.quantity += item.quantity
            
            elif old_status in ['pending', 'cancelled'] and new_status == 'completed':
                # Remove items from inventory
                for item in sale.sale_items:
                    if item.product.quantity < item.quantity:
                        flash(f'Insufficient stock for {item.product.name}. Cannot complete sale.', 'error')
                        return redirect(url_for('pos.update_sale_status', sale_id=sale_id))
                    item.product.quantity -= item.quantity
        
        sale.status = new_status
        db.session.commit()
        
        flash(f'Sale #{sale.id} status updated from {old_status} to {new_status}', 'success')
        return redirect(url_for('pos.list_sales'))
    
    return render_template('pos/update_status.html', form=form, sale=sale)

@bp.route('/receipt/<int:sale_id>')
@login_required
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('pos/receipt.html', sale=sale)

@bp.route('/sales/report')
@login_required
@manager_required
def sales_report():
    """Generate sales report with profit analysis"""
    from datetime import datetime, timedelta
    from sqlalchemy import func, and_
    
    # Get date range from query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).date()
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
    if not end_date:
        end_date = datetime.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get sales within date range
    sales_query = Sale.query.filter(
        and_(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        )
    )
    
    # Calculate totals
    total_sales = sales_query.count()
    total_revenue = sales_query.with_entities(func.sum(Sale.total_amount)).scalar() or 0
    
    # Get profit breakdown by unit type
    unit_type_stats = db.session.query(
        SaleItem.unit_type,
        func.count(SaleItem.id).label('count'),
        func.sum(SaleItem.quantity).label('total_quantity'),
        func.sum(SaleItem.price_at_sale * SaleItem.quantity).label('total_revenue'),
        func.sum((SaleItem.price_at_sale - SaleItem.cost_at_sale) * SaleItem.quantity).label('total_profit')
    ).join(Sale).filter(
        and_(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        )
    ).group_by(SaleItem.unit_type).all()
    
    # Get payment method breakdown
    payment_stats = db.session.query(
        Sale.payment_method,
        func.count(Sale.id).label('count'),
        func.sum(Sale.total_amount).label('total_amount')
    ).filter(
        and_(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        )
    ).group_by(Sale.payment_method).all()
    
    return render_template('pos/sales_report.html', 
                         start_date=start_date, 
                         end_date=end_date,
                         total_sales=total_sales,
                         total_revenue=total_revenue,
                         unit_type_stats=unit_type_stats,
                         payment_stats=payment_stats)

@bp.route('/export-sales-excel')
@login_required
@role_required(['clerk', 'manager', 'admin'])
def export_sales_excel():
    """Export sales data to Excel format"""
    try:
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        
        # Build query based on status filter
        query = Sale.query
        if status_filter != 'all':
            query = query.filter(Sale.status == status_filter)
        
        # Get all sales (not paginated for export)
        sales = query.order_by(Sale.created_at.desc()).all()
        
        if not sales:
            flash('No sales data to export', 'warning')
            return redirect(url_for('pos.list_sales'))
        
        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = f"Sales Report - {status_filter.title()}"
        
        # Set up headers
        headers = [
            'Date', 'Time', 'Invoice Number', 'Items Count', 'Total Amount', 
            'Amount Paid', 'Change Given', 'Payment Method', 'Status', 'Clerk',
            'Product Name', 'SKU', 'Unit Type', 'Quantity', 'Unit Price', 'Line Total'
        ]
        
        # Style for headers
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        
        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # Write data
        row = 2
        for sale in sales:
            # Get sale items
            if sale.sale_items:
                for i, item in enumerate(sale.sale_items):
                    # Sale info (only on first row for each sale)
                    if i == 0:
                        ws.cell(row=row, column=1, value=sale.created_at.strftime('%Y-%m-%d'))
                        ws.cell(row=row, column=2, value=sale.created_at.strftime('%H:%M:%S'))
                        ws.cell(row=row, column=3, value=sale.invoice_number)
                        ws.cell(row=row, column=4, value=len(sale.sale_items))
                        ws.cell(row=row, column=5, value=float(sale.total_amount))
                        ws.cell(row=row, column=6, value=float(sale.amount_paid))
                        ws.cell(row=row, column=7, value=float(sale.change_given))
                        ws.cell(row=row, column=8, value=sale.payment_method.title())
                        ws.cell(row=row, column=9, value=sale.status.title())
                        ws.cell(row=row, column=10, value=sale.clerk.username)
                    
                    # Item details
                    ws.cell(row=row, column=11, value=item.product.name)
                    ws.cell(row=row, column=12, value=item.product.sku)
                    ws.cell(row=row, column=13, value=item.unit_display)
                    ws.cell(row=row, column=14, value=item.quantity)
                    ws.cell(row=row, column=15, value=float(item.price_at_sale))
                    ws.cell(row=row, column=16, value=float(item.line_total))
                    
                    row += 1
            else:
                # Sale without items
                ws.cell(row=row, column=1, value=sale.created_at.strftime('%Y-%m-%d'))
                ws.cell(row=row, column=2, value=sale.created_at.strftime('%H:%M:%S'))
                ws.cell(row=row, column=3, value=sale.invoice_number)
                ws.cell(row=row, column=4, value=0)
                ws.cell(row=row, column=5, value=float(sale.total_amount))
                ws.cell(row=row, column=6, value=float(sale.amount_paid))
                ws.cell(row=row, column=7, value=float(sale.change_given))
                ws.cell(row=row, column=8, value=sale.payment_method.title())
                ws.cell(row=row, column=9, value=sale.status.title())
                ws.cell(row=row, column=10, value=sale.clerk.username)
                row += 1
        
        # Add summary row
        summary_row = row + 1
        ws.cell(row=summary_row, column=1, value="TOTALS:")
        ws.cell(row=summary_row, column=4, value=sum(len(sale.sale_items) for sale in sales))
        ws.cell(row=summary_row, column=5, value=sum(float(sale.total_amount) for sale in sales))
        ws.cell(row=summary_row, column=6, value=sum(float(sale.amount_paid) for sale in sales))
        ws.cell(row=summary_row, column=7, value=sum(float(sale.change_given) for sale in sales))
        
        # Style summary row
        for col in range(1, 17):
            cell = ws.cell(row=summary_row, column=col)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='E7E6E6', end_color='E7E6E6', fill_type='solid')
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Create response
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        filename = f"sales_report_{status_filter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Export error: {str(e)}")
        flash(f'Export failed: {str(e)}', 'danger')
        return redirect(url_for('pos.list_sales'))


@bp.route('/continue-sale/<int:sale_id>')
@login_required
#0@role_required(['clerk', 'manager', 'admin'])
def continue_sale(sale_id):
    """Continue shopping on a pending sale"""
    try:
        # Get the sale
        sale = Sale.query.get_or_404(sale_id)
        
        # Check if sale is pending
        if sale.status != 'pending':
            flash('Can only continue pending sales', 'warning')
            return redirect(url_for('pos.list_sales'))
        
        # Check permissions - users can only continue their own sales unless manager/admin
        if current_user.role == 'clerk' and sale.clerk_id != current_user.id:
            flash('You can only continue your own sales', 'danger')
            return redirect(url_for('pos.list_sales'))
        
        # Store sale ID in session for the POS page to load
        session['continue_sale_id'] = sale_id
        flash(f'Continuing sale {sale.invoice_number}', 'success')
        
        return redirect(url_for('pos.pos_page'))
        
    except Exception as e:
        current_app.logger.error(f"Continue sale error: {str(e)}")
        flash('Failed to continue sale', 'danger')
        return redirect(url_for('pos.list_sales'))


@bp.route('/load-pending-sale/<int:sale_id>')
@login_required
#@role_required(['clerk', 'manager', 'admin'])
def load_pending_sale(sale_id):
    """API endpoint to load pending sale items into cart"""
    try:
        sale = Sale.query.get_or_404(sale_id)
        
        if sale.status != 'pending':
            return jsonify({'success': False, 'error': 'Sale is not pending'})
        
        # Check permissions
        if current_user.role == 'clerk' and sale.clerk_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'})
        
        # Format sale items for the cart
        cart_items = []
        for item in sale.sale_items:
            cart_items.append({
                'id': item.product.id,
                'name': item.product.name,
                'price': float(item.price_at_sale),
                'quantity': item.quantity,
                'stock': item.product.quantity + item.quantity,  # Add back the reserved quantity
                'sku': item.product.sku,
                'unit_type': item.unit_type,
                'profit': float(item.line_profit)
            })
        
        return jsonify({
            'success': True,
            'cart_items': cart_items,
            'sale_info': {
                'id': sale.id,
                'invoice_number': sale.invoice_number,
                'payment_method': sale.payment_method,
                'amount_paid': float(sale.amount_paid)
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Load pending sale error: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to load sale'})


# Update your list_sales function to include current_time
@bp.route('/list-sales')
@login_required
#@role_required(['clerk', 'manager', 'admin'])
def list_sales():
    """Display list of sales with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    # Build query based on user role and status filter
    query = Sale.query
    
    # Regular clerks can only see their own sales
    if current_user.role == 'clerk':
        query = query.filter(Sale.clerk_id == current_user.id)
    
    # Apply status filter
    if status_filter != 'all':
        query = query.filter(Sale.status == status_filter)
    
    # Paginate results
    sales = query.order_by(Sale.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template(
        'pos/sales_list.html', 
        sales=sales, 
        status_filter=status_filter,
        current_time=datetime.now()
    )

# Add this to your pos.py file

@bp.route('/profits-dashboard')
@login_required
@manager_required
def profits_dashboard():
    """Comprehensive profits dashboard"""
    from datetime import datetime, timedelta
    from sqlalchemy import func, and_
    
    # Get date range from query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    period = request.args.get('period', '30')  # default 30 days
    
    if not start_date:
        start_date = (datetime.now() - timedelta(days=int(period))).date()
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
    if not end_date:
        end_date = datetime.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Overall profit totals
    total_sales_query = Sale.query.filter(
        and_(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        )
    )
    
    total_revenue = total_sales_query.with_entities(func.sum(Sale.total_amount)).scalar() or 0
    total_profit = total_sales_query.with_entities(func.sum(Sale.total_profit)).scalar() or 0
    total_sales_count = total_sales_query.count()
    
    # Calculate total cost (revenue - profit)
    total_cost = float(total_revenue) - float(total_profit)
    
    # Profit margin percentage
    profit_margin = (float(total_profit) / float(total_revenue) * 100) if total_revenue > 0 else 0
    
    # Daily profit breakdown - FIXED: Convert string dates back to date objects
    daily_profits_raw = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.sum(Sale.total_amount).label('revenue'),
        func.sum(Sale.total_profit).label('profit'),
        func.count(Sale.id).label('sales_count')
    ).filter(
        and_(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        )
    ).group_by(func.date(Sale.created_at)).order_by('date').all()
    
    # Convert string dates to date objects
    daily_profits = []
    for row in daily_profits_raw:
        # Convert string date to date object if it's a string
        if isinstance(row.date, str):
            date_obj = datetime.strptime(row.date, '%Y-%m-%d').date()
        else:
            date_obj = row.date
            
        daily_profits.append({
            'date': date_obj,
            'revenue': row.revenue,
            'profit': row.profit,
            'sales_count': row.sales_count
        })
    
    # FIXED: Profit by product (top performers) - using text() for ORDER BY
    product_profits = db.session.query(
        Product.name.label('product_name'),
        Product.sku.label('sku'),
        func.sum(SaleItem.quantity).label('quantity_sold'),
        func.sum((SaleItem.price_at_sale - SaleItem.cost_at_sale) * SaleItem.quantity).label('total_profit'),
        func.sum(SaleItem.price_at_sale * SaleItem.quantity).label('total_revenue')
    ).join(Sale).join(Product).filter(
        and_(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        )
    ).group_by(Product.id, Product.name, Product.sku).order_by(text('total_profit DESC')).limit(10).all()
    
    # Profit by unit type
    unit_profits = db.session.query(
        SaleItem.unit_type,
        func.sum(SaleItem.quantity).label('quantity_sold'),
        func.sum((SaleItem.price_at_sale - SaleItem.cost_at_sale) * SaleItem.quantity).label('total_profit'),
        func.sum(SaleItem.price_at_sale * SaleItem.quantity).label('total_revenue')
    ).join(Sale).filter(
        and_(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        )
    ).group_by(SaleItem.unit_type).all()
    
    # Monthly comparison (if date range > 30 days) - FIXED: Handle date conversion
    monthly_profits = []
    if (end_date - start_date).days > 30:
        monthly_profits_raw = db.session.query(
            func.strftime('%Y-%m', Sale.created_at).label('month'),
            func.sum(Sale.total_amount).label('revenue'),
            func.sum(Sale.total_profit).label('profit'),
            func.count(Sale.id).label('sales_count')
        ).filter(
            and_(
                Sale.created_at >= start_date,
                Sale.created_at <= end_date,
                Sale.status == 'completed'
            )
        ).group_by(func.strftime('%Y-%m', Sale.created_at)).order_by('month').all()
        
        # Convert to list of dictionaries for easier template handling
        monthly_profits = []
        for row in monthly_profits_raw:
            monthly_profits.append({
                'month': row.month,
                'revenue': row.revenue,
                'profit': row.profit,
                'sales_count': row.sales_count
            })
    
    return render_template('pos/profits_dashboard.html',
                         start_date=start_date,
                         end_date=end_date,
                         total_revenue=total_revenue,
                         total_profit=total_profit,
                         total_cost=total_cost,
                         total_sales_count=total_sales_count,
                         profit_margin=profit_margin,
                         daily_profits=daily_profits,
                         product_profits=product_profits,
                         unit_profits=unit_profits,
                         monthly_profits=monthly_profits,
                         period=period)