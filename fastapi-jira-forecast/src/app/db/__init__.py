# filepath: /fastapi-jira-forecast/fastapi-jira-forecast/src/app/db/__init__.py

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://user:password@localhost/dbname"  # Update with your database credentials

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()