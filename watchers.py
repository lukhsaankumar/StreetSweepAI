import time
from bson.objectid import ObjectId

def _serialize(doc: dict) -> dict:
    if doc and "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc

def watch_ticket_inserts(tickets):
    pipeline = [{"$match": {"operationType": "insert"}}]

    while True:
        try:
            with tickets.watch(pipeline) as stream:
                for change in stream:
                    doc = change.get("fullDocument", {})
                    doc = _serialize(doc)
                    print(doc)
        except Exception:
            time.sleep(2)

