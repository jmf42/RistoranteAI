
import sys
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from app.models.entities import CallLog
from app.core.config import settings

def get_latest_failed_call():
    db_url = settings.database_url
    # Use direct connection if possible or just rely on what worked before
    engine = create_engine(db_url, connect_args={"connect_timeout": 5})
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get the absolute latest call regardless of status
        print("Fetching absolute latest call...")
        latest = session.query(CallLog).order_by(desc(CallLog.started_at)).first()
        if latest:
            print(f"LATEST CALL (ID: {latest.id})")
            print(f"Time: {latest.started_at}")
            print(f"Status: {latest.call_status}")
            print(f"Outcome: {latest.outcome}")
            print(f"Summary: {latest.summary}")
            print(f"Error in extra_data: {latest.extra_data.get('error') if latest.extra_data else 'None'}")
            print("-" * 20)
            print("TRANSCRIPT:")
            print(latest.transcript_preview or "No transcript available.")
            print("-" * 20)
        else:
            print("No calls found at all.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    get_latest_failed_call()
