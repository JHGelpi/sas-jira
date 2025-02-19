from fastapi import FastAPI
from app.api.routes import router as api_router
from app.db import models
#from app.db.database import engine
from fastapi.middleware.cors import CORSMiddleware

# Create the FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router
app.include_router(api_router)

# Create the database tables
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}