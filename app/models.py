from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db
from decimal import Decimal
from sqlalchemy import func

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='cashier')  # admin, manager, cashier
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    sales = db.relationship('Sale', backref='clerk', lazy=True)
    expenses = db.relationship('Expense', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_manager(self):
        return self.role in ['admin', 'manager']
    
    def is_cashier(self):
        return self.role in ['admin', 'manager', 'cashier']
    
    def can_manage_products(self):
        """Check if user can manage products"""
        return self.role in ['admin', 'manager']
    
    def can_make_sales(self):
        """Check if user can make sales"""
        return self.role in ['cashier', 'manager', 'admin']
    
    def can_view_reports(self):
        """Check if user can view reports"""
        return self.role in ['manager', 'admin']
    
    def can_manage_expenses(self):
        """Check if user can manage expenses"""
        return self.role in ['manager', 'admin']
    
    def __repr__(self):
        return f'<User {self.username}>'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    purchase_price = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    
    # Only full_price is stored - half and quarter are calculated
    full_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Keep original price field for backward compatibility
    price = db.Column(db.Numeric(10, 2), nullable=False)  # Will be set to full_price
    
    quantity = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sale_items = db.relationship('SaleItem', backref='product', lazy=True)
    
    @property
    def half_price(self):
        """Half pack price is 50% of full pack price"""
        return float(self.full_price) * 0.5
    
    @property
    def quarter_price(self):
        """Quarter pack price is 25% of full pack price"""
        return float(self.full_price) * 0.25
    
    def get_price_for_unit(self, unit_type):
        """Get price based on unit type"""
        if unit_type == 'full':
            return float(self.full_price)
        elif unit_type == 'half':
            return self.half_price
        elif unit_type == 'quarter':
            return self.quarter_price
        return float(self.full_price)
    
    @property
    def full_pack_profit(self):
        """Calculate profit for full pack"""
        return float(self.full_price) - float(self.purchase_price)
    
    @property
    def half_pack_profit(self):
        """Half pack profit is 50% of full pack profit"""
        return self.full_pack_profit * 0.5
    
    @property
    def quarter_pack_profit(self):
        """Quarter pack profit is 25% of full pack profit"""
        return self.full_pack_profit * 0.25
    
    def get_profit_for_unit(self, unit_type):
        """Calculate profit for specific unit type"""
        if unit_type == 'full':
            return self.full_pack_profit
        elif unit_type == 'half':
            return self.half_pack_profit
        elif unit_type == 'quarter':
            return self.quarter_pack_profit
        else:
            return self.full_pack_profit
    
    def get_profit_percentage_for_unit(self, unit_type):
        """Calculate profit percentage for specific unit type"""
        if unit_type == 'full':
            cost = float(self.purchase_price)
        elif unit_type == 'half':
            cost = float(self.purchase_price) * 0.5
        elif unit_type == 'quarter':
            cost = float(self.purchase_price) * 0.25
        else:
            cost = float(self.purchase_price)
            
        if cost == 0:
            return 0
        return (self.get_profit_for_unit(unit_type) / cost) * 100
    
    @property
    def profit(self):
        """Calculate profit per full unit (for backward compatibility)"""
        return self.full_pack_profit
    
    @property
    def profit_percentage(self):
        """Calculate profit percentage for full unit (for backward compatibility)"""
        if float(self.purchase_price) == 0:
            return 0
        return (self.full_pack_profit / float(self.purchase_price)) * 100
    
    @property
    def stock_value_cost(self):
        """Calculate total stock value at cost price"""
        return float(self.purchase_price) * self.quantity

    @property
    def stock_value_retail(self):
        """Calculate total stock value at retail price"""
        return float(self.full_price) * self.quantity

    @property
    def potential_profit_value(self):
        """Calculate potential profit if all stock is sold"""
        return self.stock_value_retail - self.stock_value_cost

    @classmethod
    def get_total_stock_values(cls):
        """Get total stock values across all products"""
        result = db.session.query(
            func.sum(cls.purchase_price * cls.quantity).label('total_cost_value'),
            func.sum(cls.full_price * cls.quantity).label('total_retail_value')
        ).first()
        
        total_cost = float(result.total_cost_value or 0)
        total_retail = float(result.total_retail_value or 0)
        total_potential_profit = total_retail - total_cost
        
        return {
            'total_cost_value': total_cost,
            'total_retail_value': total_retail,
            'total_potential_profit': total_potential_profit
        }

    @classmethod
    def get_stock_statistics(cls):
        """Get comprehensive stock statistics"""
        total_products = cls.query.count()
        low_stock_count = cls.query.filter(cls.quantity <= 5).count()
        out_of_stock_count = cls.query.filter(cls.quantity == 0).count()
        in_stock_count = total_products - out_of_stock_count
        
        # Get total quantities
        total_quantity = db.session.query(func.sum(cls.quantity)).scalar() or 0
        
        return {
            'total_products': total_products,
            'in_stock_count': in_stock_count,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'total_quantity': int(total_quantity)
        }
    
    def __repr__(self):
        return f'<Product {self.name}>'

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False)
    clerk_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    total_profit = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)

    # Payment information
    payment_method = db.Column(db.String(20), nullable=False, default='cash')
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    change_given = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    
    status = db.Column(db.String(20), nullable=False, server_default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sale_items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Sale, self).__init__(**kwargs)
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
    
    @staticmethod
    def generate_invoice_number():
        """Generate invoice number with pattern INV{YEAR}{6-digit-sequence}"""
        current_year = datetime.now().year
        
        # Get the highest invoice number for the current year
        latest_sale = db.session.query(Sale).filter(
            Sale.invoice_number.like(f'INV{current_year}%')
        ).order_by(Sale.invoice_number.desc()).first()
        
        if latest_sale:
            # Extract the sequence number from the latest invoice
            sequence_str = latest_sale.invoice_number[-6:]  # Get last 6 digits
            try:
                sequence = int(sequence_str) + 1
            except ValueError:
                sequence = 1
        else:
            # First invoice of the year
            sequence = 1
        
        # Format as 6-digit number with leading zeros
        sequence_str = str(sequence).zfill(6)
        return f'INV{current_year}{sequence_str}'
    
    @property
    def calculated_profit(self):
        """Calculate total profit for this sale"""
        total = 0
        for item in self.sale_items:
            total += item.line_profit
        return total
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_cancelled(self):
        return self.status == 'cancelled'
    
    @property
    def profit_margin_percentage(self):
        """Calculate overall profit margin percentage for this sale"""
        if float(self.total_amount) > 0:
            return (float(self.total_profit) / float(self.total_amount)) * 100
        return 0
    
    def __repr__(self):
        return f'<Sale {self.id}>'

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_type = db.Column(db.String(10), nullable=False, default='full')
    price_at_sale = db.Column(db.Numeric(10, 2), nullable=False)
    cost_at_sale = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    
    @property
    def line_total(self):
        return float(self.quantity * self.price_at_sale)
    
    @property
    def line_profit(self):
        """Calculate profit for this line item"""
        return float(self.line_total) - (float(self.cost_at_sale) * self.quantity)
    
    @property
    def profit_margin_percentage(self):
        """Calculate profit margin as percentage"""
        if self.line_total > 0:
            return (self.line_profit / self.line_total) * 100
        return 0
    
    @property
    def unit_display(self):
        """Display unit type in a user-friendly way"""
        unit_map = {
            'full': 'Full Pack',
            'half': 'Half Pack',
            'quarter': 'Quarter Pack'
        }
        return unit_map.get(self.unit_type, 'Full Pack')
    
    def __repr__(self):
        return f'<SaleItem {self.id}>'

class Expense(db.Model):
    """Model for tracking business expenses"""
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receipt_number = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    CATEGORIES = [
        ('rent', 'Rent'),
        ('utilities', 'Utilities'),
        ('supplies', 'Office Supplies'),
        ('inventory', 'Inventory Purchase'),
        ('maintenance', 'Maintenance & Repairs'),
        ('marketing', 'Marketing & Advertising'),
        ('transportation', 'Transportation'),
        ('insurance', 'Insurance'),
        ('professional', 'Professional Services'),
        ('other', 'Other')
    ]
    
    def __repr__(self):
        return f'<Expense {self.description}: GHS {self.amount}>'