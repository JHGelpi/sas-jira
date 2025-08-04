from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI containerized app!"}

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Additional routes can be defined here as needed.