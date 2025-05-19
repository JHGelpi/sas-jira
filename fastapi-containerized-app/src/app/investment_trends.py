import os
from pathlib import Path

import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables (e.g., OKR_SQL_FILE, DB credentials, VIZ_DIR)
load_dotenv()

# Base directory of this script
BASE_DIR = Path(__file__).resolve().parent

# Output directory for visualizations
_viz_env = os.getenv('VIZ_DIR', 'viz_output')
VIZ_PATH = Path(_viz_env)
if not VIZ_PATH.is_absolute():
    VIZ_PATH = BASE_DIR / VIZ_PATH
VIZ_PATH.mkdir(parents=True, exist_ok=True)

# Database URL (e.g., postgresql://user:pass@host:port/dbname)
db_url = os.getenv('DATABASE_URL')
if not db_url:
    raise EnvironmentError("DATABASE_URL environment variable must be set.")


def load_sql(path):
    """Read an external SQL file and return its contents as a string."""
    with open(path, 'r') as f:
        return f.read()


def fetch_data(sql_file=None):
    """
    Fetch data by executing SQL in the given file using a SQLAlchemy engine.
    """
    # Determine SQL filename: env or fallback
    filename = sql_file or os.getenv('OKR_SQL_FILE', 'okr_summary.sql')
    sql_path = (BASE_DIR / filename).resolve()
    sql_statement = load_sql(sql_path)

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(sql_statement), conn)
    finally:
        engine.dispose()
    return df


def preprocess(df):
    """Convert normalized_sprint to numeric for sorting."""
    df['sprint_order'] = df['normalized_sprint'].astype(float)
    return df


def plot_by_category(df):
    """Generate and save one line chart per investment_category."""
    df = preprocess(df)
    for cat, sub in df.groupby('investment_category'):
        sub_sorted = sub.sort_values('sprint_order', ascending=True)
        fig = px.line(
            sub_sorted,
            x='normalized_sprint',
            y='pct_of_sprint_total',
            title=f"{cat} — % of Sprint Total",
            markers=True
        )
        fig.update_layout(
            xaxis_title="Normalized Sprint",
            yaxis_title="% of Sprint Total",
            xaxis=dict(
                categoryorder='array',
                categoryarray=sub_sorted['normalized_sprint']
            )
        )
        # Save chart to file
        safe_name = cat.replace(' ', '_').replace('/', '_')
        out_file = VIZ_PATH / f"{safe_name}.html"
        fig.write_html(out_file)
        print(f"Saved chart for {cat} to {out_file}")


def plot_master(df):
    """Generate and save a master line chart for all categories."""
    df = preprocess(df)
    df_sorted = df.sort_values('sprint_order', ascending=True)
    fig = px.line(
        df_sorted,
        x='normalized_sprint',
        y='pct_of_sprint_total',
        color='investment_category',
        title="All Categories — % of Sprint Total",
        markers=True
    )
    fig.update_layout(
        xaxis_title="Normalized Sprint",
        yaxis_title="% of Sprint Total",
        xaxis=dict(
            categoryorder='array',
            categoryarray=df_sorted['normalized_sprint'].unique()
        )
    )
    out_file = VIZ_PATH / "all_categories.html"
    fig.write_html(out_file)
    print(f"Saved master chart to {out_file}")


def trends_main():
    df = fetch_data()
    print(df.head())
    plot_by_category(df)
    plot_master(df)


if __name__ == "__main__":
    trends_main()
