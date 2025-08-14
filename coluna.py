from app import db
from app import Pessoa  # ou o nome do seu modelo

columns = Pessoa.__table__.columns.keys()
print(columns)