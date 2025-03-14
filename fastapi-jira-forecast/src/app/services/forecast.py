from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import requests

from app.db.models import Forecast
from app.utils import calculate_confidence_intervals

JIRA_API_URL = "https://your-jira-instance.atlassian.net/rest/api/2/search"

def fetch_jira_data(project_key: str, session: Session):
    headers = {
        "Authorization": "Bearer YOUR_JIRA_API_TOKEN",
        "Content-Type": "application/json"
    }
    query = {
        "jql": f"project = {project_key} AND status = Done",
        "fields": ["id", "created", "resolved"],
        "maxResults": 1000
    }
    response = requests.get(JIRA_API_URL, headers=headers, params=query)
    response.raise_for_status()
    return response.json().get("issues", [])

def analyze_closing_rate(issues):
    closing_dates = []
    for issue in issues:
        if "resolved" in issue["fields"]:
            closing_dates.append(datetime.strptime(issue["fields"]["resolved"], "%Y-%m-%dT%H:%M:%S.%f%z"))
    
    if not closing_dates:
        return None, None

    closing_dates.sort()
    closing_rate = len(closing_dates) / len(issues)
    return closing_dates, closing_rate

def forecast_completion_date(closing_dates, closing_rate):
    if not closing_dates:
        return None

    last_closing_date = closing_dates[-1]
    days_to_complete = (1 / closing_rate) * 30  # Assuming 30 days to complete based on rate
    forecast_date = last_closing_date + timedelta(days=days_to_complete)
    return forecast_date

def update_forecast_in_db(project_issue_id: str, forecast_date: datetime, session: Session):
    confidence_intervals = calculate_confidence_intervals(forecast_date)
    midpoint = (confidence_intervals[0] + confidence_intervals[1]) / 2

    forecast_entry = Forecast(
        project_issue_id=project_issue_id,
        confidence_interval_low=confidence_intervals[0],
        confidence_interval_high=confidence_intervals[1],
        midpoint=midpoint,
        forecast_date=forecast_date
    )
    session.add(forecast_entry)
    session.commit()

def process_project_forecast(project_key: str, session: Session):
    issues = fetch_jira_data(project_key, session)
    closing_dates, closing_rate = analyze_closing_rate(issues)
    forecast_date = forecast_completion_date(closing_dates, closing_rate)

    if forecast_date:
        update_forecast_in_db(project_key, forecast_date, session)