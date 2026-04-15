
import psycopg
import os
from dotenv import load_dotenv

def check_latest():
    # Load from root .env
    load_dotenv("../.env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not found")
        return
        
    try:
        # Use a short timeout
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                print("Fetching last 3 calls from call_logs...")
                cur.execute("SELECT id, started_at, call_status, outcome, summary FROM call_logs ORDER BY started_at DESC LIMIT 3")
                rows = cur.fetchall()
                for row in rows:
                    print(f"ID: {row[0]}, Time: {row[1]}, Status: {row[2]}, Outcome: {row[3]}, Summary: {row[4]}")
                
                print("\nFetching last 3 webhook errors...")
                cur.execute("SELECT id, source, status, last_error FROM raw_webhook_events WHERE status = 'error' OR last_error IS NOT NULL ORDER BY received_at DESC LIMIT 3")
                rows = cur.fetchall()
                for row in rows:
                    print(f"ID: {row[0]}, Source: {row[1]}, Status: {row[2]}, Error: {row[3]}")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_latest()
