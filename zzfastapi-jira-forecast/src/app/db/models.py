from sqlalchemy import Column, Integer, Float, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ProjectForecast(Base):
    __tablename__ = 'project_forecast'

    id = Column(Integer, primary_key=True, index=True)
    project_issue_id = Column(String, index=True, nullable=False)
    confidence_interval_low = Column(Float, nullable=False)
    confidence_interval_high = Column(Float, nullable=False)
    midpoint = Column(Float, nullable=False)

    def __repr__(self):
        return f"<ProjectForecast(project_issue_id={self.project_issue_id}, " \
               f"confidence_interval_low={self.confidence_interval_low}, " \
               f"confidence_interval_high={self.confidence_interval_high}, " \
               f"midpoint={self.midpoint})>"