from app import db
from sqlalchemy import text

# Check if column exists
result = db.engine.execute(text("PRAGMA table_info(user);")).fetchall()
columns = [column[1] for column in result]

if 'is_active' not in columns:
    # Add the column
    db.engine.execute(text("ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT TRUE;"))
    # Update existing users
    db.engine.execute(text("UPDATE user SET is_active = TRUE WHERE is_active IS NULL;"))
    db.session.commit()
    print("Migration completed!")
else:
    print("Column already exists!")

exit()