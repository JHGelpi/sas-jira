from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Issue(Base):
    __tablename__ = 'issues'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class Initiative(Base):
    __tablename__ = 'initiatives'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)