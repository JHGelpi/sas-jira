import os
import logging
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from sqlalchemy import create_engine, text
import shutil

# Use the centralized logging system
logger = logging.getLogger(__name__)

def main():
    """Generates the bug trend charts from the snapshot data."""
    logger.info("Starting bug chart generation...")
    
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL is not set. Aborting chart generation.")
        return

    try:
        engine = create_engine(db_url)
        conn = engine.connect()
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        return

    try:
        # --- Reverted to a single, broad query to fetch all data first ---
        logger.info("Fetching all bug snapshot data from the last 6 months...")
        six_months_ago = date.today() - timedelta(days=180)
        sql = text("""
            SELECT * FROM tbl_bug_snapshots 
            WHERE issue_type = 'Bug' AND snapshot_date >= :start_date
        """)
        df = pd.read_sql(sql, conn, params={'start_date': six_months_ago})
        logger.info(f"Fetched {len(df)} total bug snapshot records.")
        
    except Exception as e:
        logger.error(f"Failed to fetch data from database: {e}")
        return
    finally:
        conn.close()
        
    if df.empty:
        logger.warning("No data found to generate charts.")
        return

    # --- Chart 1: Outstanding CRP Bugs (Column Chart) ---
    # Filter the main dataframe in Python for CRP bugs
    df_crp = df[df['origin'].str.contains('CRP', na=False) & (df['status_category'] != 'Done')].copy()
    
    if not df_crp.empty:
        # --- Define a more muted, modern color palette ---
        color_palette = {
            'COMPDIV': '#1f77b4', 'COMPTRIAGE': '#ff7f0e', 'COMPLANG': '#2ca02c',
            'COMPUTESVCS': '#d62728', 'COMPWLM': '#9467bd', 'COMPHOST': '#8c564b',
            'COMPBEIJING': '#e377c2', 'GEMINI': '#7f7f7f', 'COMPSRVCORE': '#bcbd22',
            'COMPCONNECT': '#17becf', 'COMPOBSERVE': '#aec7e8', 'COMPDIVPUNE': '#ffbb78',
            'COMPSRVCAS': '#98df8a'
        }
        
        daily_counts = df_crp.groupby(['snapshot_date', 'project_key']).size().reset_index(name='open_bugs')
        fig1 = px.bar(daily_counts, x='snapshot_date', y='open_bugs', color='project_key',
                      title='Daily Open CRP Bugs (Last 6 Months)',
                      labels={'snapshot_date': 'Date', 'open_bugs': 'Number of Open Bugs', 'project_key': 'Project'},
                      color_discrete_map=color_palette) # Apply the new color palette
        fig1.update_xaxes(type='date')
    else:
        fig1 = None
        logger.warning("No data found for the 'Outstanding CRP Bugs' chart.")

    # --- Chart 2: Bugs by Release (Grouped with Project Hover Info) ---
    # Filter the main dataframe for the latest snapshot date
    df_latest = df[df['snapshot_date'] == df['snapshot_date'].max()].copy()

    if not df_latest.empty:
        df_latest['is_crp'] = df_latest['origin'].str.contains('CRP', na=False)
        df_latest['state'] = df_latest['status_category'].apply(lambda x: 'Open' if x != 'Done' else 'Closed')
        df_latest['release'] = df_latest['affects_version'].str.split(',').str[0].str.strip()
        
        bugs_by_release_detailed = df_latest.groupby(['release', 'project_key', 'is_crp', 'state']).size().reset_index(name='count')

        hover_text_df = bugs_by_release_detailed.groupby(['release', 'state']).apply(
            lambda g: '<br>'.join([f"{row.project_key}: {row['count']}" for _, row in g.iterrows()])
        ).reset_index(name='project_breakdown')

        bugs_by_release_agg = bugs_by_release_detailed.groupby(['release', 'state'])['count'].sum().reset_index()
        chart_df = pd.merge(bugs_by_release_agg, hover_text_df, on=['release', 'state'])

        fig2 = px.bar(chart_df, x='release', y='count', color='state',
                      title='CRP Bugs by Release (Current Snapshot)',
                      labels={'release': 'Release Version', 'count': 'Number of Bugs', 'state': 'Status'},
                      category_orders={'release': sorted(chart_df['release'].dropna().unique())},
                      barmode='group',
                      custom_data=['project_breakdown'])
        
        fig2.update_traces(
            hovertemplate="<b>Release:</b> %{x}<br><b>Status:</b> %{data.name}<br><b>Total Bugs:</b> %{y}<br><b>Project Breakdown:</b><br>%{customdata[0]}<extra></extra>"
        )
    else:
        fig2 = None
        logger.warning("No data found for the 'Bugs by Release' chart.")

    # --- Generate HTML ---
    report_dir = os.getenv('JIRA_REPORT_DIR', './reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "bug_trends_report.html")

    try:
        with open(report_path, 'w') as f:
            f.write("<html><head><title>CRP Bug Trends Report</title></head><body>")
            f.write("<h1>CRP Bug Trends Report</h1>")
            if fig1:
                f.write(fig1.to_html(full_html=False, include_plotlyjs='cdn'))
            if fig2:
                f.write(fig2.to_html(full_html=False, include_plotlyjs='cdn'))
            f.write("</body></html>")
        logger.info(f"Successfully generated bug trends report at {report_path}")
    except Exception as e:
        logger.error(f"Failed to write HTML report: {e}")
        return

    homepage_dir = os.getenv('HOMEPAGE_REPORTS_DIR')
    if homepage_dir:
        try:
            shutil.copy(report_path, homepage_dir)
            logger.info(f"Successfully copied report to {homepage_dir}")
        except Exception as e:
            logger.error(f"Failed to copy report to homepage directory: {e}")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=dotenv_path)
    main()

