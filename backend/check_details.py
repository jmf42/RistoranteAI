
import psycopg
import os
import json
from dotenv import load_dotenv

def check_details(call_ids):
    load_dotenv("../.env")
    url = os.environ.get("DATABASE_URL")
    
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for call_id in call_ids:
                    print(f"\n=== DETAILS FOR CALL {call_id} ===")
                    cur.execute("SELECT transcript_preview, extra_data, summary FROM call_logs WHERE id = %s", (call_id,))
                    row = cur.fetchone()
                    if row:
                        print(f"Summary: {row[2]}")
                        print("Transcript:")
                        print(row[0])
                        print("Extra Data (parsed):")
                        try:
                            # If it's already a dict, just print it. If it's a string, load it.
                            extra = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                            # Only print interesting parts to avoid flooding
                            print(json.dumps({
                                "error": extra.get("error"),
                                "tool_events": extra.get("tool_events"),
                                "conversation_summary": extra.get("conversation_summary"),
                                "transferred_to_restaurant": extra.get("transferred_to_restaurant"),
                                "escalation_reason": extra.get("escalation_reason")
                            }, indent=2))
                        except Exception as je:
                            print(f"Error parsing extra_data: {je}")
                    else:
                        print("Call not found.")
                    print("-" * 50)
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_details(["ccc8eca9-a001-431d-b0c3-ef0fb06db601", "e603dedf-f5b8-447b-81f6-af99466e65c5"])
