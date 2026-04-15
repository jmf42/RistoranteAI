
from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker
from app.models.entities import CallLog, RawWebhookEvent
from app.core.config import settings

def check_counts():
    db_url = settings.database_url
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        call_count = session.query(func.count(CallLog.id)).scalar()
        webhook_count = session.query(func.count(RawWebhookEvent.id)).scalar()
        print(f"Total CallLogs: {call_count}")
        print(f"Total WebhookEvents: {webhook_count}")
        
        last_call = session.query(CallLog).order_by(desc(CallLog.started_at)).first()
        if last_call:
            print(f"Last Call Start: {last_call.started_at}, ID: {last_call.id}, Status: {last_call.call_status}")
            
        last_webhook = session.query(RawWebhookEvent).order_by(desc(RawWebhookEvent.received_at)).first()
        if last_webhook:
            print(f"Last Webhook: {last_webhook.received_at}, Source: {last_webhook.source}, Status: {last_webhook.status}")

    finally:
        session.close()

if __name__ == "__main__":
    check_counts()
