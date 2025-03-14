from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import Forecast
from app.services.forecast import calculate_forecast
import requests

JIRA_API_URL = "https://your-jira-instance.atlassian.net/rest/api/2/search"

def fetch_jira_data(project_key: str, session: Session):
    headers = {
        "Authorization": "Bearer YOUR_JIRA_API_TOKEN",
        "Content-Type": "application/json"
    }
    query = {
        "jql": f"project = {project_key} AND status = Done",
        "fields": "id,summary,status,created,updated",
        "maxResults": 1000
    }
    response = requests.get(JIRA_API_URL, headers=headers, params=query)
    response.raise_for_status()
    return response.json()

def analyze_completion_rate(jira_data):
    # Analyze the rate of closing stories
    closed_dates = [datetime.strptime(issue['fields']['updated'], '%Y-%m-%dT%H:%M:%S.%f%z') for issue in jira_data['issues']]
    completion_rate = len(closed_dates) / len(jira_data['issues']) if jira_data['issues'] else 0
    return completion_rate, closed_dates

def forecast_completion_dates(completion_rate, closed_dates):
    # Forecast completion dates based on the completion rate
    if completion_rate == 0:
        return None, None
    days_to_complete = (1 / completion_rate) * len(closed_dates)
    forecast_date = datetime.now() + timedelta(days=days_to_complete)
    return forecast_date, days_to_complete

def update_forecast_in_db(project_issue_id: str, forecast_date: datetime, session: Session):
    # Update the forecast in the database
    forecast = Forecast(
        project_issue_id=project_issue_id,
        forecast_date=forecast_date,
        confidence_interval_low=forecast_date - timedelta(days=3),
        confidence_interval_high=forecast_date + timedelta(days=3),
        midpoint=forecast_date
    )
    session.add(forecast)
    session.commit()

def daily_forecast_update(project_key: str, session: Session):
    jira_data = fetch_jira_data(project_key, session)
    completion_rate, closed_dates = analyze_completion_rate(jira_data)
    forecast_date, _ = forecast_completion_dates(completion_rate, closed_dates)
    
    if forecast_date:
        update_forecast_in_db(project_key, forecast_date, session)