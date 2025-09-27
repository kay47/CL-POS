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
    sku = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    purchase_price = db.Column(db.Numeric(10, 2), nullable=False)
    full_price = db.Column(db.Numeric(10, 2), nullable=False)
    half_price = db.Column(db.Numeric(10, 2), nullable=True)  # ADD THIS FIELD
    price = db.Column(db.Numeric(10, 2), nullable=False)  # For backward compatibility
    quantity = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to sales
    sale_items = db.relationship('SaleItem', backref='product', lazy=True)
    
    # Define product categories
    CATEGORIES = [
        ('electronics', 'Electronics'),
        ('clothing', 'Clothing'),
        ('food', 'Food & Beverages'),
        ('beauty', 'Beauty & Personal Care'),
        ('books', 'Books & Stationery'),
        ('home', 'Home & Garden'),
        ('sports', 'Sports & Recreation'),
        ('automotive', 'Automotive'),
        ('toys', 'Toys & Games'),
        ('health', 'Health & Wellness'),
        ('jewelry', 'Jewelry & Accessories'),
        ('music', 'Music & Instruments'),
        ('pets', 'Pet Supplies'),
        ('office', 'Office Supplies'),
        ('tools', 'Tools & Hardware'),
        ('other', 'Other')
    ]
    
    @staticmethod
    def generate_sku(category):
        """Generate a unique SKU based on category prefix + sequential number"""
        # Get category prefix (first 3 letters, uppercase)
        category_prefix = category.upper()[:3]
        
        # Find the highest existing SKU number for this category
        existing_skus = db.session.query(Product.sku).filter(
            Product.sku.like(f'{category_prefix}%')
        ).all()
        
        if not existing_skus:
            # First product in this category
            next_number = 1
        else:
            # Extract numbers from existing SKUs and find the highest
            numbers = []
            for (sku,) in existing_skus:
                try:
                    # Extract the numeric part after the category prefix
                    number_part = sku[3:]  # Remove first 3 letters
                    if number_part.isdigit():
                        numbers.append(int(number_part))
                except (ValueError, IndexError):
                    continue
            
            next_number = max(numbers, default=0) + 1
        
        # Format as 4-digit number with leading zeros
        return f"{category_prefix}{next_number:04d}"
    
    @classmethod
    def create_with_auto_sku(cls, name, category, description=None, purchase_price=0, 
                           full_price=0, half_price=None, quantity=0):
        """Create a new product with auto-generated SKU"""
        # Generate unique SKU
        sku = cls.generate_sku(category)
        
        # Ensure SKU is unique (in case of race conditions)
        counter = 1
        original_sku = sku
        while cls.query.filter_by(sku=sku).first():
            # Extract base and number
            base = original_sku[:3]
            base_number = int(original_sku[3:])
            sku = f"{base}{(base_number + counter):04d}"
            counter += 1
        
        # Auto-calculate half_price if not provided
        if half_price is None and full_price:
            half_price = Decimal(str(full_price)) / Decimal('2')
        
        # Create the product
        product = cls(
            sku=sku,
            name=name,
            category=category,
            description=description or '',
            purchase_price=Decimal(str(purchase_price)),
            full_price=Decimal(str(full_price)),
            half_price=Decimal(str(half_price)) if half_price else None,
            price=Decimal(str(full_price)),  # Backward compatibility
            quantity=quantity
        )
        
        return product
    
    def get_price_for_unit(self, unit_type='full'):
        """Get price based on unit type"""
        if unit_type == 'half':
            return self.half_price if self.half_price else (self.full_price / Decimal('2'))
        elif unit_type == 'quarter':
            return self.full_price / Decimal('4')
        else:  # full
            return self.full_price
    
    def get_profit_for_unit(self, unit_type='full'):
        """Calculate profit for a unit type"""
        selling_price = self.get_price_for_unit(unit_type)
        if unit_type == 'half':
            cost = self.purchase_price / Decimal('2')
        elif unit_type == 'quarter':
            cost = self.purchase_price / Decimal('4')
        else:  # full
            cost = self.purchase_price
        
        return selling_price - cost
    
    @property
    def category_display(self):
        """Get human-readable category name"""
        category_dict = dict(self.CATEGORIES)
        return category_dict.get(self.category, self.category.title())
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.full_price > 0:
            profit = self.full_price - self.purchase_price
            return (profit / self.full_price) * 100
        return 0
    
    @property
    def is_low_stock(self):
        """Check if product is low on stock"""
        return self.quantity <= 5
    
    @property
    def is_out_of_stock(self):
        """Check if product is out of stock"""
        return self.quantity <= 0
    
    @property
    def quarter_price(self):
        """Calculate quarter price as 25% of full price"""
        return self.full_price / Decimal('4')
    
    @property
    def calculated_half_price(self):
        """Get half price, using stored value or calculating from full price"""
        return self.half_price if self.half_price else (self.full_price / Decimal('2'))
    
    @property
    def profit_per_quarter(self):
        """Calculate profit for quarter pack"""
        return self.quarter_price - (self.purchase_price / Decimal('4'))
    
    @property
    def profit_per_half(self):
        """Calculate profit for half pack"""
        half_price = self.calculated_half_price
        return half_price - (self.purchase_price / Decimal('2'))
    
    @property
    def profit_per_full(self):
        """Calculate profit for full pack"""
        return self.full_price - self.purchase_price
    
    def __repr__(self):
        return f'<Product {self.sku}: {self.name}>'

# Rest of your models remain the same...
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