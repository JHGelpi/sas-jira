# FastAPI Jira Forecast

This project is a FastAPI application that analyzes the rate of closing Jira stories for a given project, forecasts completion dates, and stores the results in a PostgreSQL database. The application calculates and updates forecasts daily based on activity.

## Project Structure

```
fastapi-jira-forecast
├── src
│   ├── main.py                  # Entry point of the FastAPI application
│   ├── app
│   │   ├── __init__.py          # Initializes the app package
│   │   ├── api
│   │   │   └── routes.py        # Defines API routes for fetching forecasts
│   │   ├── db
│   │   │   ├── __init__.py      # Initializes the database package
│   │   │   └── models.py        # Defines database models for forecasts
│   │   ├── services
│   │   │   ├── __init__.py      # Initializes the services package
│   │   │   └── forecast.py      # Contains logic for analyzing Jira data
│   │   ├── utils.py             # Utility functions for the application
│   │   └── project_completion_forecast.py # Main logic for project completion forecast
│   └── tests
│       ├── __init__.py          # Initializes the tests package
│       └── test_main.py         # Unit tests for the application
├── alembic
│   ├── env.py                   # Sets up the environment for database migrations
│   ├── script.py.mako           # Template for generating migration scripts
│   └── versions
│       └── README               # Information about database schema versions
├── Dockerfile                    # Instructions for building a Docker image
├── docker-compose.yml            # Defines services for running the application
├── requirements.txt              # Lists Python dependencies
├── alembic.ini                  # Configuration file for Alembic
└── README.md                    # Documentation for the project
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd fastapi-jira-forecast
   ```

2. **Create a virtual environment:**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Set up the PostgreSQL database:**
   - Ensure PostgreSQL is installed and running.
   - Create a database for the application.

5. **Run database migrations:**
   ```
   alembic upgrade head
   ```

6. **Start the application:**
   ```
   uvicorn src.main:app --reload
   ```

## Usage

- Access the API documentation at `http://localhost:8000/docs`.
- Use the endpoints to fetch project completion forecasts and related data.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or features.

## License

This project is licensed under the MIT License. See the LICENSE file for details.