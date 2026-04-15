
import sys
import os
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from app.models.entities import CallLog, RawWebhookEvent
from app.core.config import settings

def check_latest_calls():
    db_url = settings.database_url
    print(f"Connecting to: {db_url.split('@')[-1]}")
    
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("\n=== LATEST CALL LOGS ===")
        latest_calls = session.query(CallLog).order_by(desc(CallLog.started_at)).limit(5).all()
        for call in latest_calls:
            print("-" * 50)
            print(f"ID: {call.id}")
            print(f"Started At: {call.started_at}")
            print(f"Status: {call.call_status}")
            print(f"Outcome: {call.outcome}")
            print(f"Summary: {call.summary}")
            if call.extra_data:
                print(f"Extra Data: {call.extra_data}")
            
        print("\n=== LATEST WEBHOOK EVENTS ===")
        latest_webhooks = session.query(RawWebhookEvent).order_by(desc(RawWebhookEvent.received_at)).limit(5).all()
        for webhook in latest_webhooks:
            print("-" * 50)
            print(f"ID: {webhook.id}")
            print(f"Source: {webhook.source}")
            print(f"Status: {webhook.status}")
            print(f"Received At: {webhook.received_at}")
            if webhook.last_error:
                print(f"Last Error: {webhook.last_error}")
            # print(f"Payload: {webhook.raw_payload}")
            
    finally:
        session.close()

if __name__ == "__main__":
    check_latest_calls()
