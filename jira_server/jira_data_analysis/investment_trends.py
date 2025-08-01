import os
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
VIZ_PATH = BASE_DIR / os.getenv('VIZ_DIR', 'viz_output')
VIZ_PATH.mkdir(parents=True, exist_ok=True)

# Setup database engine
DB_URL = os.getenv('DATABASE_URL')
if not DB_URL:
    raise EnvironmentError("DATABASE_URL environment variable must be set.")
ENGINE = create_engine(DB_URL)

def fetch_data(sql_file_path: Path) -> pd.DataFrame:
    """Fetches data by executing an SQL file."""
    print(f"Fetching data from SQL file: {sql_file_path.name}")
    try:
        with open(sql_file_path, 'r') as f:
            sql_statement = f.read()
        
        with ENGINE.connect() as conn:
            return pd.read_sql_query(text(sql_statement), conn)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Converts normalized_sprint to a numeric type for correct sorting."""
    if 'normalized_sprint' in df.columns:
        # Using errors='coerce' will turn non-numeric sprints into NaN, which can be handled
        df['sprint_order'] = pd.to_numeric(df['normalized_sprint'], errors='coerce')
        df.dropna(subset=['sprint_order'], inplace=True) # Drop rows where conversion failed
    return df

def plot_by_category(df: pd.DataFrame):
    """Generates and saves one line chart per investment_category."""
    print("Generating charts per investment category...")
    for cat, sub_df in df.groupby('investment_category'):
        sub_sorted = sub_df.sort_values('sprint_order', ascending=True)
        fig = px.line(
            sub_sorted,
            x='normalized_sprint',
            y='pct_of_sprint_total',
            title=f"{cat} — % of Sprint Total",
            markers=True,
            labels={'normalized_sprint': 'Normalized Sprint', 'pct_of_sprint_total': '% of Sprint Total'}
        )
        fig.update_layout(xaxis=dict(type='category')) # Ensures sprint numbers are treated as categories
        
        safe_name = cat.replace(' ', '_').replace('/', '_').lower()
        out_file = VIZ_PATH / f"{safe_name}.html"
        fig.write_html(out_file)
        print(f"Saved chart: {out_file}")

def plot_master(df: pd.DataFrame):
    """Generate and save a master line chart for all categories."""
    print("Generating master chart for all categories...")
    df_sorted = df.sort_values('sprint_order', ascending=True)
    
    fig = px.line(
        df_sorted,
        x='normalized_sprint',
        y='pct_of_sprint_total',
        color='investment_category',
        title="All Categories — % of Sprint Total",
        markers=True,
        labels={'normalized_sprint': 'Normalized Sprint', 'pct_of_sprint_total': '% of Sprint Total'}
    )
    fig.update_layout(xaxis=dict(type='category'))
    
    out_file = VIZ_PATH / "all_categories_master.html"
    fig.write_html(out_file)
    print(f"Saved master chart: {out_file}")

def main():
    """Main function to run the investment trends report generation."""
    # Determine SQL file path
    sql_filename = os.getenv('OKR_SQL_FILE', 'okr_summary.sql')
    sql_path = (BASE_DIR / sql_filename).resolve()

    if not sql_path.exists():
        print(f"Error: SQL file not found at {sql_path}")
        return
        
    df_raw = fetch_data(sql_path)
    
    if df_raw.empty:
        print("No data fetched. Aborting visualization.")
        return

    # Preprocess the data ONCE
    df_processed = preprocess(df_raw)
    
    # Pass the processed DataFrame to plotting functions
    plot_by_category(df_processed)
    plot_master(df_processed)
    print("Investment trends report generation complete.")

if __name__ == "__main__":
    main()