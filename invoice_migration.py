# invoice_migration.py
# Script to add invoice_number column and populate existing sales

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app import create_app, db
from app.models import Sale
from datetime import datetime

def add_invoice_number_column():
    """Add invoice_number column to sales table (works for SQLite & MySQL/Postgres)"""
    app = create_app()
    
    with app.app_context():
        print("Adding invoice_number column to sales table...")

        try:
            with db.engine.connect() as conn:
                dialect = db.engine.url.get_dialect().name  # e.g. "sqlite", "mysql", "postgresql"

                column_exists = False

                if dialect == "sqlite":
                    # SQLite → use PRAGMA
                    result = conn.execute(db.text("PRAGMA table_info(sale)"))
                    columns = [row[1] for row in result]  # row[1] is column name
                    column_exists = "invoice_number" in columns

                else:
                    # MySQL/Postgres → use information_schema
                    result = conn.execute(db.text("""
                        SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_name = 'sale' AND column_name = 'invoice_number'
                    """))
                    column_exists = result.scalar() > 0

                if not column_exists:
                    conn.execute(db.text("ALTER TABLE sale ADD COLUMN invoice_number VARCHAR(20)"))
                    print("✅ Added invoice_number column")
                else:
                    print("ℹ️ invoice_number column already exists")

        except Exception as e:
            print(f"❌ Failed to add column: {str(e)}")
            raise


def populate_invoice_numbers():
    """Populate invoice numbers for existing sales"""
    app = create_app()
    
    with app.app_context():
        print("Populating invoice numbers for existing sales...")

        try:
            # Get all sales without invoice numbers, ordered by creation date
            sales = Sale.query.filter(
                (Sale.invoice_number == None) | (Sale.invoice_number == '')
            ).order_by(Sale.created_at.asc()).all()
            
            print(f"Found {len(sales)} sales without invoice numbers")

            # Group sales by year for sequential numbering
            sales_by_year = {}
            for sale in sales:
                year = sale.created_at.year
                if year not in sales_by_year:
                    sales_by_year[year] = []
                sales_by_year[year].append(sale)

            # Generate invoice numbers for each year
            for year, year_sales in sales_by_year.items():
                print(f"Processing {len(year_sales)} sales for year {year}")
                
                for i, sale in enumerate(year_sales, 1):
                    sequence_str = str(i).zfill(6)
                    invoice_number = f'INV{year}{sequence_str}'
                    
                    # Avoid duplicates
                    existing = Sale.query.filter_by(invoice_number=invoice_number).first()
                    if existing and existing.id != sale.id:
                        j = i + 1
                        while True:
                            sequence_str = str(j).zfill(6)
                            test_invoice = f'INV{year}{sequence_str}'
                            if not Sale.query.filter_by(invoice_number=test_invoice).first():
                                invoice_number = test_invoice
                                break
                            j += 1
                    
                    sale.invoice_number = invoice_number
                    print(f"  Sale ID {sale.id} -> {invoice_number}")

            # Add unique constraint (safe for SQLite/Postgres/MySQL)
            try:
                with db.engine.connect() as conn:
                    dialect = db.engine.url.get_dialect().name

                    if dialect == "sqlite":
                        conn.execute(db.text("""
                            CREATE UNIQUE INDEX IF NOT EXISTS idx_sale_invoice_number 
                            ON sale (invoice_number)
                        """))
                    else:
                        conn.execute(db.text("""
                            DO $$
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM pg_indexes 
                                    WHERE tablename='sale' AND indexname='idx_sale_invoice_number'
                                ) THEN
                                    CREATE UNIQUE INDEX idx_sale_invoice_number ON sale (invoice_number);
                                END IF;
                            END$$;
                        """))
                    print("✅ Added unique constraint on invoice_number")

            except Exception as e:
                print(f"⚠️ Warning: Could not add unique constraint: {str(e)}")

            db.session.commit()
            print("✅ All invoice numbers populated successfully!")

            # Verification
            print("\n--- Verification ---")
            recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(5).all()
            for sale in recent_sales:
                print(f"Sale ID {sale.id}: {sale.invoice_number} - {sale.created_at}")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Failed to populate invoice numbers: {str(e)}")
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("INVOICE NUMBER MIGRATION")
    print("=" * 60)
    print("This script will:")
    print("1. Add invoice_number column to the sale table")
    print("2. Generate invoice numbers for existing sales")
    print("3. Format: INV{YEAR}{6-digit-sequence} (e.g., INV2025000001)")
    print()
    
    confirm = input("Do you want to proceed? (yes/no): ").lower().strip()
    
    if confirm in ['yes', 'y']:
        try:
            # Step 1: Add column
            add_invoice_number_column()
            
            # Step 2: Populate existing sales
            populate_invoice_numbers()
            
            print("\n🎉 Migration completed successfully!")
            print("All sales now have unique invoice numbers.")
            print("New sales will automatically get invoice numbers when created.")
            
        except Exception as e:
            print(f"\n💥 Migration failed: {str(e)}")
            print("Please check your database connection and try again.")
            
    else:
        print("Migration cancelled.")
