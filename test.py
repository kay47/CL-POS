from app import db
from app.models import User

print(User.__table__.columns.keys())
