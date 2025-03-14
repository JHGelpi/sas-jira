def format_date(date):
    return date.strftime("%Y-%m-%d")

def calculate_confidence_interval(data, confidence=0.80):
    import numpy as np
    import scipy.stats as stats

    mean = np.mean(data)
    std_dev = np.std(data)
    n = len(data)
    
    z_score = stats.norm.ppf((1 + confidence) / 2)
    margin_of_error = z_score * (std_dev / np.sqrt(n))
    
    return (mean - margin_of_error, mean + margin_of_error), mean

def parse_jira_data(jira_data):
    # Assuming jira_data is a list of dictionaries with relevant fields
    return [(item['issue_id'], item['closed_date']) for item in jira_data]

def calculate_midpoint(interval):
    return (interval[0] + interval[1]) / 2

def daily_update_schedule():
    from datetime import datetime, timedelta
    return datetime.now() + timedelta(days=1)