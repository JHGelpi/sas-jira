from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from app.db.models import Forecast
from app.services.forecast import calculate_forecast

router = APIRouter()

@router.get("/forecasts/{project_id}")
async def get_forecast(project_id: str, db: Session):
    try:
        forecast_data = calculate_forecast(project_id, db)
        if not forecast_data:
            raise HTTPException(status_code=404, detail="Forecast not found")
        return forecast_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/forecasts/")
async def create_forecast(project_id: str, db: Session):
    try:
        forecast = Forecast(project_id=project_id)
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        return forecast
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))