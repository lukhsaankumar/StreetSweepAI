import os
import time
import requests
from dotenv import load_dotenv
from bson.objectid import ObjectId

load_dotenv()

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

def _serialize(doc: dict) -> dict:
    if "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc

def watch_ticket_inserts(tickets):
    pipeline = [{"$match": {"operationType": "insert"}}]

    while True:
        try:
            with tickets.watch(pipeline) as stream:
                for change in stream:
                    doc = change["fullDocument"]
                    payload = {
                        "type": "ticket_created",
                        "ticket": _serialize(doc)
                    }

                    if WEBHOOK_URL:
                        requests.post(WEBHOOK_URL, json=payload, timeout=3)

        except Exception:
            time.sleep(2)
