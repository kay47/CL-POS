from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite # Import if needed, but usually not required for this fix

def upgrade():
    with op.batch_alter_table('sale', schema=None, copy_from=None) as batch_op:
        batch_op.add_column(sa.Column('total_profit', sa.Numeric(precision=10, scale=2), server_default=sa.text('0.00'), nullable=False))