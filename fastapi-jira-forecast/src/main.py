from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router

app = FastAPI()

# Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Jira Project Completion Forecast API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)