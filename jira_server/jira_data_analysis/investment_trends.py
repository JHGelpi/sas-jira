# jira_data_analysis/investment_trends.py
"""
Investment trends visualization.

This module generates Plotly charts showing how different investment categories
(IRIS, PM Initiatives, Bugs, Operational) trend over sprints.
"""

import os
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from logging_utils import get_logger, log_section_header

logger = get_logger(__name__)

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

BASE_DIR = Path(__file__).resolve().parent
VIZ_PATH = BASE_DIR / os.getenv('VIZ_DIR', 'viz_output')
VIZ_PATH.mkdir(parents=True, exist_ok=True)

# Setup database engine
DB_URL = os.getenv('DATABASE_URL')
if not DB_URL:
    raise EnvironmentError("DATABASE_URL environment variable must be set")
ENGINE = create_engine(DB_URL)


def fetch_data(sql_file_path: Path) -> pd.DataFrame:
    """Fetches data by executing an SQL file."""
    logger.searching(f"Fetching data from SQL file: {sql_file_path.name}")
    try:
        with open(sql_file_path, 'r') as f:
            sql_statement = f.read()
        
        with ENGINE.connect() as conn:
            df = pd.read_sql_query(text(sql_statement), conn)
        logger.success(f"Fetched {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return pd.DataFrame()


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Converts ship_cadence to a numeric type for correct sorting."""
    if 'ship_cadence' in df.columns:
        logger.processing("Preprocessing data: converting ship cadence values")
        df['sprint_order'] = pd.to_numeric(df['ship_cadence'], errors='coerce')
        df.dropna(subset=['sprint_order'], inplace=True)
        logger.info(f"After preprocessing: {len(df)} rows")
    return df


def plot_by_category(df: pd.DataFrame):
    """Generates and saves one line chart per investment_category."""
    logger.processing("Generating charts per investment category")

    for cat, sub_df in df.groupby('investment_category'):
        logger.debug(f"Creating chart for category: {cat}")
        sub_sorted = sub_df.sort_values('sprint_order', ascending=True)
        fig = px.line(
            sub_sorted,
            x='ship_cadence',
            y='pct_of_sprint_total',
            title=f"{cat} – % of Sprint Total",
            markers=True,
            labels={'ship_cadence': 'Ship Cadence', 'pct_of_sprint_total': '% of Sprint Total'}
        )
        fig.update_layout(xaxis=dict(type='category'))

        safe_name = cat.replace(' ', '_').replace('/', '_').lower()
        out_file = VIZ_PATH / f"{safe_name}.html"
        fig.write_html(out_file)
        logger.success(f"Saved chart: {out_file}")


def plot_master(df: pd.DataFrame):
    """Generate and save a master line chart for all categories."""
    logger.processing("Generating master chart for all categories")

    df_sorted = df.sort_values('sprint_order', ascending=True)

    fig = px.line(
        df_sorted,
        x='ship_cadence',
        y='pct_of_sprint_total',
        color='investment_category',
        title="All Categories – % of Sprint Total",
        markers=True,
        labels={'ship_cadence': 'Ship Cadence', 'pct_of_sprint_total': '% of Sprint Total'}
    )
    fig.update_layout(xaxis=dict(type='category'))

    out_file = VIZ_PATH / "all_categories_master.html"
    fig.write_html(out_file)
    logger.success(f"Saved master chart: {out_file}")


def main():
    """Main function to run the investment trends report generation."""
    log_section_header(logger, "INVESTMENT TRENDS REPORT")
    
    logger.start("Starting investment trends report generation")
    
    # Determine SQL file path
    sql_filename = os.getenv('OKR_SQL_FILE', 'okr_summary.sql')
    sql_path = (BASE_DIR / sql_filename).resolve()

    if not sql_path.exists():
        logger.error(f"SQL file not found at {sql_path}")
        return
        
    df_raw = fetch_data(sql_path)
    
    if df_raw.empty:
        logger.warning("No data fetched. Aborting visualization")
        return

    # Preprocess the data ONCE
    df_processed = preprocess(df_raw)
    
    if df_processed.empty:
        logger.warning("No data after preprocessing. Aborting visualization")
        return
    
    # Pass the processed DataFrame to plotting functions
    plot_by_category(df_processed)
    plot_master(df_processed)
    
    logger.complete("Investment trends report generation complete")


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()
    main()