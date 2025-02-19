from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def log_current_time():
    logger.info(f"Current time: {datetime.now()}")

def start_scheduler():
    scheduler.add_job(log_current_time, 'interval', seconds=60)
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()