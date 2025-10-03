from flask import Blueprint, render_template, request, make_response, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models import Sale, SaleItem, Product, User
from app.decorators import manager_required, admin_required
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import csv
from io import StringIO

bp = Blueprint('reports', __name__)

@bp.route('/')
@login_required
@manager_required
def sales_reports():
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    clerk_id = request.args.get('clerk_id')
    report_type = request.args.get('report_type', 'daily')
    
    # Default date range (last 7 days)
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Build query
    query = Sale.query.filter(Sale.status == 'completed')  # Only completed sales
    
    # Date filter
    if start_date:
        query = query.filter(Sale.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Sale.created_at < end_date_obj)
    
    # Clerk filter
    if clerk_id:
        query = query.filter(Sale.clerk_id == int(clerk_id))
    
    # Get sales data
    sales = query.order_by(desc(Sale.created_at)).limit(50).all()
    
    # Calculate summary statistics - INCLUDING total_profit
    total_sales = query.count()
    total_revenue = query.with_entities(func.sum(Sale.total_amount)).scalar() or 0
    total_profit = query.with_entities(func.sum(Sale.total_profit)).scalar() or 0
    average_sale = float(total_revenue) / total_sales if total_sales > 0 else 0
    
    # Get top products - Convert Row objects to dictionaries
    top_products_query = db.session.query(
        Product.id,
        Product.name,
        Product.sku,
        func.sum(SaleItem.quantity).label('total_quantity'),
        func.sum(SaleItem.quantity * SaleItem.price_at_sale).label('total_revenue'),
        func.sum((SaleItem.price_at_sale - SaleItem.cost_at_sale) * SaleItem.quantity).label('total_profit')
    ).join(SaleItem).join(Sale).filter(
        Sale.created_at >= datetime.strptime(start_date, '%Y-%m-%d'),
        Sale.created_at < (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)),
        Sale.status == 'completed'
    ).group_by(Product.id, Product.name, Product.sku).order_by(desc('total_revenue')).limit(20).all()
    
    # Convert to dictionaries
    top_products = [
        {
            'name': row.name,
            'sku': row.sku,
            'total_quantity': int(row.total_quantity),
            'total_revenue': float(row.total_revenue),
            'total_profit': float(row.total_profit or 0)
        }
        for row in top_products_query
    ]
    
    # Get clerk performance - Convert Row objects to dictionaries
    clerk_performance_query = db.session.query(
        User.id,
        User.username,
        func.count(Sale.id).label('total_sales'),
        func.sum(Sale.total_amount).label('total_revenue'),
        func.sum(Sale.total_profit).label('total_profit')
    ).join(Sale).filter(
        Sale.created_at >= datetime.strptime(start_date, '%Y-%m-%d'),
        Sale.created_at < (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)),
        Sale.status == 'completed'
    ).group_by(User.id, User.username).order_by(desc('total_revenue')).all()
    
    # Convert to dictionaries
    clerk_performance = [
        {
            'id': row.id,
            'username': row.username,
            'total_sales': int(row.total_sales),
            'total_revenue': float(row.total_revenue),
            'total_profit': float(row.total_profit or 0)
        }
        for row in clerk_performance_query
    ]
    
    # Get daily sales data for chart - Convert Row objects to dictionaries
    daily_sales_query = db.session.query(
        func.date(Sale.created_at).label('sale_date'),
        func.count(Sale.id).label('total_sales'),
        func.sum(Sale.total_amount).label('total_revenue'),
        func.sum(Sale.total_profit).label('total_profit')
    ).filter(
        Sale.created_at >= datetime.strptime(start_date, '%Y-%m-%d'),
        Sale.created_at < (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)),
        Sale.status == 'completed'
    ).group_by(func.date(Sale.created_at)).order_by('sale_date').all()
    
    # Convert to dictionaries
    daily_sales = []
    for row in daily_sales_query:
        # Handle different date formats
        if hasattr(row.sale_date, 'strftime'):
            date_str = row.sale_date.strftime('%Y-%m-%d')
        elif isinstance(row.sale_date, str):
            date_str = row.sale_date
        else:
            date_str = str(row.sale_date)
        
        daily_sales.append({
            'sale_date': date_str,
            'total_sales': int(row.total_sales),
            'total_revenue': float(row.total_revenue),
            'total_profit': float(row.total_profit or 0)
        })
    
    # Get unit type performance
    unit_type_stats = db.session.query(
        SaleItem.unit_type,
        func.sum(SaleItem.quantity).label('total_quantity'),
        func.sum(SaleItem.price_at_sale * SaleItem.quantity).label('total_revenue'),
        func.sum((SaleItem.price_at_sale - SaleItem.cost_at_sale) * SaleItem.quantity).label('total_profit')
    ).join(Sale).filter(
        Sale.created_at >= datetime.strptime(start_date, '%Y-%m-%d'),
        Sale.created_at < (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)),
        Sale.status == 'completed'
    ).group_by(SaleItem.unit_type).all()
    
    # Get payment method breakdown
    payment_stats = db.session.query(
        Sale.payment_method,
        func.count(Sale.id).label('count'),
        func.sum(Sale.total_amount).label('total_amount')
    ).filter(
        Sale.created_at >= datetime.strptime(start_date, '%Y-%m-%d'),
        Sale.created_at < (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)),
        Sale.status == 'completed'
    ).group_by(Sale.payment_method).all()
    
    # Get all clerks for filter dropdown
    clerks = User.query.filter(User.is_active == True).order_by(User.username).all()
    
    return render_template('reports/sales_report.html',
                         sales=sales,
                         start_date=start_date,
                         end_date=end_date,
                         clerk_id=clerk_id,
                         total_sales=total_sales,
                         total_revenue=total_revenue,
                         total_profit=total_profit,  # THIS WAS MISSING!
                         average_sale=average_sale,
                         top_products=top_products,
                         clerk_performance=clerk_performance,
                         daily_sales=daily_sales,
                         unit_type_stats=unit_type_stats,
                         payment_stats=payment_stats,
                         clerks=clerks)

@bp.route('/export')
@login_required
@manager_required
def export_sales():
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    clerk_id = request.args.get('clerk_id')
    export_format = request.args.get('format', 'csv')
    
    # Build query
    query = Sale.query.join(User)
    
    if start_date:
        query = query.filter(Sale.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Sale.created_at < end_date_obj)
    if clerk_id:
        query = query.filter(Sale.clerk_id == int(clerk_id))
    
    sales = query.order_by(desc(Sale.created_at)).all()
    
    if export_format == 'csv':
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Sale ID', 'Date', 'Time', 'Clerk', 'Total Amount', 'Items Count'])
        
        # Write data
        for sale in sales:
            writer.writerow([
                sale.id,
                sale.created_at.strftime('%Y-%m-%d'),
                sale.created_at.strftime('%H:%M:%S'),
                sale.clerk.username,
                float(sale.total_amount),
                len(sale.sale_items)
            ])
        
        # Create response
        output.seek(0)
        # Handle missing dates for filename
        fname_start = start_date if start_date else 'all'
        fname_end = end_date if end_date else 'all'
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=sales_report_{fname_start}_to_{fname_end}.csv'
        return response

    elif export_format == 'xlsx':
        import openpyxl
        import io
        from flask import send_file

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Sales Report"

        # Header row
        headers = ["Sale ID", "Date", "Time", "Clerk", "Total Amount", "Items Count"]
        sheet.append(headers)

        # Data rows
        for sale in sales:
            sheet.append([
                sale.id,
                sale.created_at.strftime('%Y-%m-%d'),
                sale.created_at.strftime('%H:%M:%S'),
                sale.clerk.username,
                float(sale.total_amount),
                len(sale.sale_items)
            ])

        # Save to memory
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)

        fname_start = start_date if start_date else 'all'
        fname_end = end_date if end_date else 'all'
        return send_file(
            output,
            as_attachment=True,
            download_name=f"sales_report_{fname_start}_to_{fname_end}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Default to showing report page
    return redirect(url_for('reports.sales_reports', 
                          start_date=start_date, 
                          end_date=end_date, 
                          clerk_id=clerk_id))

@bp.route('/detailed/<int:sale_id>')
@login_required
@manager_required
def detailed_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('reports/detailed_sale.html', sale=sale)

@bp.route('/delete/<int:sale_id>', methods=['POST'])
@login_required
@admin_required
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    
    try:
        # Delete associated sale items first (due to foreign key constraints)
        SaleItem.query.filter_by(sale_id=sale_id).delete()
        
        # Store sale info for flash message
        sale_info = f"Sale #{sale.id} from {sale.created_at.strftime('%Y-%m-%d %H:%M')} (${sale.total_amount:.2f})"
        
        # Delete the sale
        db.session.delete(sale)
        db.session.commit()
        
        flash(f'Successfully deleted {sale_info}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting sale: {str(e)}', 'error')
    
    return redirect(url_for('reports.sales_reports'))

@bp.route('/delete/<int:sale_id>/confirm')
@login_required
@admin_required
def confirm_delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('reports/confirm_delete.html', sale=sale)

@bp.route('/bulk-delete', methods=['POST'])
@login_required
@admin_required
def bulk_delete_sales():
    """Allow admin to delete multiple sales at once"""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    sale_ids = request.json.get('sale_ids', [])
    
    if not sale_ids:
        return jsonify({'error': 'No sales selected'}), 400
    
    try:
        deleted_count = 0
        for sale_id in sale_ids:
            # Delete associated sale items first
            SaleItem.query.filter_by(sale_id=sale_id).delete()
            # Delete the sale
            sale = Sale.query.get(sale_id)
            if sale:
                db.session.delete(sale)
                deleted_count += 1
        
        db.session.commit()
        flash(f'Successfully deleted {deleted_count} sales', 'success')
        return jsonify({'success': True, 'deleted_count': deleted_count})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500 