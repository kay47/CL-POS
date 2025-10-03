import sqlite3

DB_FILE = "pos.db"

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table});")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def migrate():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("Starting manual migration...")

    # Product table migrations
    if not column_exists(cursor, "product", "units_per_pack"):
        print("Adding column: product.units_per_pack")
        cursor.execute("ALTER TABLE product ADD COLUMN units_per_pack INTEGER NOT NULL DEFAULT 1;")
    else:
        print("Column already exists: product.units_per_pack")

    if not column_exists(cursor, "product", "unit_price"):
        print("Adding column: product.unit_price")
        cursor.execute("ALTER TABLE product ADD COLUMN unit_price NUMERIC(10,2);")
    else:
        print("Column already exists: product.unit_price")

    # Expense table migrations
    if not column_exists(cursor, "expense", "document_filename"):
        print("Adding column: expense.document_filename")
        cursor.execute("ALTER TABLE expense ADD COLUMN document_filename VARCHAR(255);")
    else:
        print("Column already exists: expense.document_filename")

    if not column_exists(cursor, "expense", "document_path"):
        print("Adding column: expense.document_path")
        cursor.execute("ALTER TABLE expense ADD COLUMN document_path VARCHAR(500);")
    else:
        print("Column already exists: expense.document_path")

    if not column_exists(cursor, "expense", "document_size"):
        print("Adding column: expense.document_size")
        cursor.execute("ALTER TABLE expense ADD COLUMN document_size INTEGER;")
    else:
        print("Column already exists: expense.document_size")

    if not column_exists(cursor, "expense", "document_type"):
        print("Adding column: expense.document_type")
        cursor.execute("ALTER TABLE expense ADD COLUMN document_type VARCHAR(100);")
    else:
        print("Column already exists: expense.document_type")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
