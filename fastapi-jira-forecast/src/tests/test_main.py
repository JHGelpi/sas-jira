from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Jira Project Completion Forecast API"}

def test_forecast_endpoint():
    response = client.get("/forecast?project_id=123")
    assert response.status_code == 200
    assert "project_issue_id" in response.json()
    assert "confidence_interval" in response.json()
    assert "midpoint" in response.json()

def test_invalid_forecast_endpoint():
    response = client.get("/forecast?project_id=invalid")
    assert response.status_code == 422  # Unprocessable Entity for invalid input

def test_forecast_calculation():
    # Assuming there's a function in the forecast service to calculate forecasts
    from app.services.forecast import calculate_forecast
    result = calculate_forecast(project_id=123, closing_rate=0.5)
    assert result["project_issue_id"] == 123
    assert "confidence_interval" in result
    assert "midpoint" in result

def test_database_connection():
    from app.db.models import get_db_session
    session = get_db_session()
    assert session is not None
    session.close()