from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db
from decimal import Decimal
from sqlalchemy import func
import secrets
import string
import os

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='cashier')  # admin, manager, cashier
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # New fields for temporary password functionality
    is_temporary_password = db.Column(db.Boolean, default=False, nullable=False)
    password_reset_token = db.Column(db.String(100), nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    last_password_change = db.Column(db.DateTime, nullable=True)

    # Relationships
    sales = db.relationship('Sale', backref='clerk', lazy=True)
    expenses = db.relationship('Expense', backref='user', lazy=True)

    def set_password(self, password, is_temporary=False):
        """Set password with option to mark as temporary"""
        self.password_hash = generate_password_hash(password)
        self.is_temporary_password = is_temporary
        self.must_change_password = is_temporary
        self.last_password_change = datetime.utcnow()
    
        self.password_reset_token = None
        self.password_reset_expires = None
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @staticmethod
    def generate_temporary_password(length=8):
        """Generate a secure temporary password"""
        characters = string.ascii_letters + string.digits
        characters = characters.replace('0', '').replace('O', '').replace('l', '').replace('1', '').replace('I', '')
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    def generate_password_reset_token(self, expires_in=3600):
        """Generate a password reset token that expires"""
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        return token
    
    def verify_reset_token(self, token):
        """Verify if the reset token is valid and not expired"""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        
        if datetime.utcnow() > self.password_reset_expires:
            self.password_reset_token = None
            self.password_reset_expires = None
            return False
        
        return self.password_reset_token == token
    
    def needs_password_change(self):
        """Check if user needs to change their password"""
        return self.must_change_password or self.is_temporary_password
    
    def is_password_expired(self, max_age_days=90):
        """Check if password has expired (optional feature)"""
        if not self.last_password_change:
            return True
        
        expiry_date = self.last_password_change + timedelta(days=max_age_days)
        return datetime.utcnow() > expiry_date
    
    def complete_password_change(self, new_password):
        """Complete the password change process"""
        self.set_password(new_password, is_temporary=False)
        self.is_temporary_password = False
        self.must_change_password = False
        self.last_password_change = datetime.utcnow()
        
        self.password_reset_token = None
        self.password_reset_expires = None
        
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
    half_price = db.Column(db.Numeric(10, 2), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # For backward compatibility

    units_per_pack = db.Column(db.Integer, default=1, nullable=False)  # How many units in a full pack
    unit_price = db.Column(db.Numeric(10, 2), nullable=True)  # Price per single unit (retail)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # Product image fields
    image_filename = db.Column(db.String(255), nullable=True)
    image_path = db.Column(db.String(500), nullable=True)
    
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

    # Image configuration
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @property
    def has_image(self):
        """Check if product has an image"""
        return self.image_filename is not None and self.image_path is not None
    
    @property
    def image_url(self):
        """Get URL for product image"""
        if self.has_image:
            return f'/static/uploads/product_images/{self.image_filename}'
        return '/static/images/no-product-image.png'  # Default placeholder
    
    @property
    def total_units_available(self):
        """Calculate total units available (packs * units_per_pack)"""
        return float(self.quantity) * self.units_per_pack
    
    @staticmethod
    def allowed_image_file(filename):
        """Check if image file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Product.ALLOWED_IMAGE_EXTENSIONS
    
    @staticmethod
    def generate_sku(category):
        """Generate a unique SKU based on category prefix + sequential number"""
        category_prefix = category.upper()[:3]
        
        existing_skus = db.session.query(Product.sku).filter(
            Product.sku.like(f'{category_prefix}%')
        ).all()
        
        if not existing_skus:
            next_number = 1
        else:
            numbers = []
            for (sku,) in existing_skus:
                try:
                    number_part = sku[3:]
                    if number_part.isdigit():
                        numbers.append(int(number_part))
                except (ValueError, IndexError):
                    continue
            
            next_number = max(numbers, default=0) + 1
        
        return f"{category_prefix}{next_number:04d}"
    
    @classmethod
    def create_with_auto_sku(cls, name, category, description=None, purchase_price=0, 
                           full_price=0, half_price=None, quantity=0):
        """Create a new product with auto-generated SKU"""
        sku = cls.generate_sku(category)
        
        counter = 1
        original_sku = sku
        while cls.query.filter_by(sku=sku).first():
            base = original_sku[:3]
            base_number = int(original_sku[3:])
            sku = f"{base}{(base_number + counter):04d}"
            counter += 1
        
        if half_price is None and full_price:
            half_price = Decimal(str(full_price)) / Decimal('2')
        
        product = cls(
            sku=sku,
            name=name,
            category=category,
            description=description or '',
            purchase_price=Decimal(str(purchase_price)),
            full_price=Decimal(str(full_price)),
            half_price=Decimal(str(half_price)) if half_price else None,
            price=Decimal(str(full_price)),
            quantity=quantity
        )
        
        return product
    
    def get_price_for_unit(self, unit_type='full'):
        """Get price based on unit type"""
        if unit_type == 'unit':
            # Return custom unit price if set, otherwise calculate from full price
            return self.calculated_unit_price
        elif unit_type == 'half':
            return self.half_price if self.half_price else (self.full_price / Decimal('2'))
        elif unit_type == 'quarter':
            return self.full_price / Decimal('4')
        else:  # full
            return self.full_price
    
    def get_profit_for_unit(self, unit_type='full'):
        """Calculate profit for a unit type"""
        selling_price = self.get_price_for_unit(unit_type)
        
        if unit_type == 'unit':
            # Cost per unit = purchase price / units per pack
            cost = self.purchase_price / Decimal(str(self.units_per_pack))
        elif unit_type == 'half':
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
    
    def calculate_inventory_deduction(self, quantity, unit_type):
        """
        Calculate how many packs to deduct from inventory based on unit type
        
        Args:
            quantity: Number of units being sold
            unit_type: 'full', 'half', 'quarter', or 'unit'
        
        Returns:
            Decimal: Number of packs to deduct from inventory
        """
        if unit_type == 'full':
            # Selling full packs - deduct 1 pack per quantity
            return Decimal(str(quantity))
        
        elif unit_type == 'half':
            # Selling half packs - deduct 0.5 pack per quantity
            return Decimal(str(quantity)) * Decimal('0.5')
        
        elif unit_type == 'quarter':
            # Selling quarter packs - deduct 0.25 pack per quantity
            return Decimal(str(quantity)) * Decimal('0.25')
        
        elif unit_type == 'unit':
            # Selling individual units - deduct fractional pack
            # Example: Selling 3 units from a 12-pack = 3/12 = 0.25 packs
            if self.units_per_pack and self.units_per_pack > 0:
                return Decimal(str(quantity)) / Decimal(str(self.units_per_pack))
            else:
                # Fallback: if units_per_pack not set, treat as full pack
                return Decimal(str(quantity))
        
        else:
            # Default: treat as full pack
            return Decimal(str(quantity))
        
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
    
    @property
    def profit_per_unit(self):
        """Calculate profit for single retail unit"""
        return self.get_profit_for_unit('unit')
    
    @property
    def calculated_unit_price(self):
        """Get unit price, calculating if not set"""
        if self.unit_price:
            return self.unit_price
        # Calculate from full price divided by units per pack
        return self.full_price / Decimal(str(self.units_per_pack))
    
    @property
    def cost_per_unit(self):
        """Calculate cost per single unit"""
        return self.purchase_price / Decimal(str(self.units_per_pack))
    
    def __repr__(self):
        return f'<Product {self.sku}: {self.name}>'


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
        
        latest_sale = db.session.query(Sale).filter(
            Sale.invoice_number.like(f'INV{current_year}%')
        ).order_by(Sale.invoice_number.desc()).first()
        
        if latest_sale:
            sequence_str = latest_sale.invoice_number[-6:]
            try:
                sequence = int(sequence_str) + 1
            except ValueError:
                sequence = 1
        else:
            sequence = 1
        
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
        return f'<Sale {self.invoice_number}>'


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)  # Allows for 0.5, 0.25, etc.
    unit_type = db.Column(db.String(10), nullable=False, default='full')  # full, half, quarter, unit
    price_at_sale = db.Column(db.Numeric(10, 2), nullable=False)
    cost_at_sale = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    
    @property
    def line_total(self):
        """Calculate total for this line item"""
        return float(self.quantity * self.price_at_sale)
    
    @property
    def line_cost(self):
        """Calculate total cost for this line item"""
        return float(self.quantity * self.cost_at_sale)
    
    @property
    def line_profit(self):
        """Calculate profit for this line item"""
        return self.line_total - self.line_cost
    
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
            'quarter': 'Quarter Pack',
            'unit': 'Retail Unit'
        }
        return unit_map.get(self.unit_type, 'Full Pack')
    
    @property
    def inventory_deducted(self):
        """Calculate how much inventory was deducted for this sale item"""
        if self.unit_type == 'unit':
            return float(self.quantity) / float(self.product.units_per_pack)
        elif self.unit_type == 'half':
            return float(self.quantity) * 0.5
        elif self.unit_type == 'quarter':
            return float(self.quantity) * 0.25
        else:  # full
            return float(self.quantity)
    
    def __repr__(self):
        return f'<SaleItem {self.id}: {self.quantity} x {self.unit_display} of {self.product.name}>'


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

    # File upload fields
    document_filename = db.Column(db.String(255))
    document_path = db.Column(db.String(500))
    document_size = db.Column(db.Integer)
    document_type = db.Column(db.String(100))

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
    
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    
    @staticmethod
    def allowed_file(filename):
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Expense.ALLOWED_EXTENSIONS
    
    @property
    def has_document(self):
        """Check if expense has an attached document"""
        return self.document_filename is not None
    
    @property
    def document_size_kb(self):
        """Get document size in KB"""
        if self.document_size:
            return round(self.document_size / 1024, 2)
        return 0
    
    def __repr__(self):
        return f'<Expense {self.description}: GHS {self.amount}>'