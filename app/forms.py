from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, DecimalField, IntegerField, SubmitField, BooleanField, DateField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError, Optional, EqualTo
from app.models import User, Product
from datetime import datetime

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    role = SelectField('Role', choices=[
        ('cashier', 'Cashier'),
        ('manager', 'Manager'),
        ('admin', 'Administrator')
    ], default='cashier')
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Choose a different one.')

class ProductForm(FlaskForm):
    # Add SKU field for editing existing products
    sku = StringField(
        'SKU',
        validators=[DataRequired(), Length(min=1, max=20)],
        render_kw={'readonly': True}  # Make it readonly since it's auto-generated
    )
    
    category = SelectField(
        'Category',
        choices=Product.CATEGORIES,
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    name = StringField(
        'Product Name',
        validators=[DataRequired(), Length(min=1, max=100)],
        render_kw={'placeholder': 'Enter product name...'}
    )
    
    description = TextAreaField(
        'Description',
        validators=[Length(max=500)],
        render_kw={'rows': 3, 'placeholder': 'Optional product description...'}
    )
    
    purchase_price = DecimalField(
        'Purchase Price (GHS)',
        validators=[DataRequired(), NumberRange(min=0, max=999999.99)],
        places=2,
        render_kw={'step': '0.01', 'min': '0', 'placeholder': '0.00'}
    )
    
    full_price = DecimalField(
        'Selling Price (GHS)',
        validators=[DataRequired(), NumberRange(min=0, max=999999.99)],
        places=2,
        render_kw={'step': '0.01', 'min': '0', 'placeholder': '0.00'}
    )
    
    # Add half_price field
    half_price = DecimalField(
        'Half Price (GHS)',
        validators=[Optional(), NumberRange(min=0, max=999999.99)],
        places=2,
        render_kw={'step': '0.01', 'min': '0', 'placeholder': '0.00'}
    )

    # Add quarter_price field
    quarter_price = DecimalField(
        'Quarter Price (GHS)',
        validators=[Optional(), NumberRange(min=0, max=999999.99)],
        places=2,
        render_kw={'step': '0.01', 'min': '0', 'placeholder': '0.00'}
)
    
    quantity = IntegerField(
        'Initial Stock Quantity',
        validators=[DataRequired(), NumberRange(min=0, max=999999)],
        default=0,
        render_kw={'min': '0', 'placeholder': '0'}
    )
    
    submit = SubmitField('Save Product')
    
    def __init__(self, original_sku=None, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.original_sku = original_sku
        
        # For new products, remove the SKU field requirement
        if not self.sku.data:
            self.sku.validators = []
    
    def validate_purchase_price(self, field):
        if field.data >= self.full_price.data:
            raise ValidationError('Purchase price must be less than selling price.')
    
    def validate_full_price(self, field):
        if field.data <= self.purchase_price.data:
            raise ValidationError('Selling price must be greater than purchase price.')
    
    def validate_half_price(self, field):
        if field.data and field.data >= self.full_price.data:
            raise ValidationError('Half price must be less than full price.')
    
    # And add this validation method:
    def validate_quarter_price(self, field):
        if field.data:
            if field.data >= self.half_price.data:
                raise ValidationError('Quarter price must be less than half price.')
        if field.data >= self.full_price.data:
            raise ValidationError('Quarter price must be less than full price.')
        
class EditUserForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=20, message="Username must be between 3 and 20 characters")
    ])
    
    role = SelectField('Role', choices=[
        ('cashier', 'Cashier'),
        ('manager', 'Manager'),
        ('admin', 'Administrator')
    ], validators=[DataRequired()])
    
    password = PasswordField('New Password (leave blank to keep current)', validators=[
        Optional(),
        Length(min=6, message="Password must be at least 6 characters long")
    ])
    
    password_confirm = PasswordField('Confirm New Password', validators=[
        EqualTo('password', message='Passwords must match')
    ])
    
    is_active = BooleanField('Active User')
    
    submit = SubmitField('Update User')

class ExpenseForm(FlaskForm):
    category = SelectField('Category', validators=[DataRequired()], choices=[
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
    ])
    
    description = StringField('Description', validators=[
        DataRequired(), 
        Length(max=200, message="Description must be less than 200 characters")
    ])
    
    amount = DecimalField('Amount (GHS)', validators=[
        DataRequired(), 
        NumberRange(min=0.01, message="Amount must be greater than 0")
    ], places=2)
    
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    
    receipt_number = StringField('Receipt Number', validators=[
        Optional(), 
        Length(max=50, message="Receipt number must be less than 50 characters")
    ])
    
    notes = TextAreaField('Additional Notes', validators=[Optional()])
    
    submit = SubmitField('Save Expense')

class SaleStatusForm(FlaskForm):
    status = SelectField('Status', choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], validators=[DataRequired()])
    
    submit = SubmitField('Update Status')

class PaymentForm(FlaskForm):
    """Form for processing payment during checkout"""
    payment_method = SelectField('Payment Method', choices=[
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer')
    ], validators=[DataRequired()], default='cash')
    
    amount_paid = DecimalField('Amount Paid (GHS)', validators=[
        DataRequired(), 
        NumberRange(min=0.01, message="Amount paid must be greater than 0")
    ], places=2)
    
    submit = SubmitField('Process Payment')