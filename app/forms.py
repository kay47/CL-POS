from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, DecimalField, IntegerField, SubmitField, BooleanField, DateField, HiddenField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError, Optional, EqualTo, Email
from app.models import User, Product
from datetime import datetime

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    
    role = SelectField('Role', choices=[
        ('cashier', 'Cashier'),
        ('manager', 'Manager'),
        ('admin', 'Administrator')
    ], default='cashier')

    # Note: Password is now generated automatically
    generate_password = BooleanField('Generate Temporary Password', default=True, 
                                   render_kw={'disabled': True, 'checked': True})
    
    # Optional email for password reset notifications
    email = StringField('Email (Optional)', validators=[Optional(), Email()], 
                       render_kw={'placeholder': 'user@example.com'})
    
    submit = SubmitField('Create User')  # Changed from 'Register' to 'Create User'
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Choose a different one.')

class ChangePasswordForm(FlaskForm):
    """Form for users to change their own password"""
    current_password = PasswordField('Current Password', 
                                   validators=[DataRequired()],
                                   render_kw={'placeholder': 'Enter your current password'})
    
    new_password = PasswordField('New Password', 
                                validators=[
                                    DataRequired(), 
                                    Length(min=8, message="Password must be at least 8 characters long")
                                ],
                                render_kw={'placeholder': 'Enter new password'})
    
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[
                                       DataRequired(),
                                       EqualTo('new_password', message='Passwords must match')
                                   ],
                                   render_kw={'placeholder': 'Confirm new password'})
    
    submit = SubmitField('Change Password')
    
    def validate_current_password(self, field):
        """Validate that the current password is correct"""
        from flask_login import current_user
        if not current_user.check_password(field.data):
            raise ValidationError('Current password is incorrect.')
    
    def validate_new_password(self, field):
        """Ensure new password is different from current password"""
        from flask_login import current_user
        if current_user.check_password(field.data):
            raise ValidationError('New password must be different from your current password.')

class FirstTimePasswordChangeForm(FlaskForm):
    """Form for first-time password change with temporary password"""
    username = StringField('Username', validators=[DataRequired()],
                          render_kw={'readonly': True})
    
    temporary_password = PasswordField('Temporary Password', 
                                     validators=[DataRequired()],
                                     render_kw={'placeholder': 'Enter the temporary password given to you'})
    
    new_password = PasswordField('New Password', 
                                validators=[
                                    DataRequired(), 
                                    Length(min=8, message="Password must be at least 8 characters long")
                                ],
                                render_kw={'placeholder': 'Create your new password'})
    
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[
                                       DataRequired(),
                                       EqualTo('new_password', message='Passwords must match')
                                   ],
                                   render_kw={'placeholder': 'Confirm your new password'})
    
    submit = SubmitField('Set New Password')

class ForgotPasswordForm(FlaskForm):
    """Form to request password reset"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)],
                          render_kw={'placeholder': 'Enter your username'})
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    """Form to reset password with token"""
    token = HiddenField('Token', validators=[DataRequired()])
    
    new_password = PasswordField('New Password', 
                                validators=[
                                    DataRequired(), 
                                    Length(min=8, message="Password must be at least 8 characters long")
                                ],
                                render_kw={'placeholder': 'Enter your new password'})
    
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[
                                       DataRequired(),
                                       EqualTo('new_password', message='Passwords must match')
                                   ],
                                   render_kw={'placeholder': 'Confirm your new password'})
    
    submit = SubmitField('Reset Password')

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

    # Admin can reset user password (generates new temporary password)
    reset_password = BooleanField('Reset Password (Generate New Temporary Password)')
    
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