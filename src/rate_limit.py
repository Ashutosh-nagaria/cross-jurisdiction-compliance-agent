"""
A shared daily budget guard for the public deployment of this app.

This project costs a small amount of real money every time a question
is actually asked, since it calls Voyage AI, Anthropic, and MongoDB
Atlas. Once this app is publicly reachable, anyone with the link could
otherwise ask an unlimited number of questions. This module enforces a
small shared daily limit, tracked in MongoDB, the same database this
project already uses, so the limit is shared across every visitor
combined, not given separately to each person who opens the page.

The limit resets at midnight UTC, and one question to one system,
whether asked directly or as part of comparing all three, counts as
one unit against the shared daily total.
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

DAILY_LIMIT = 20
DATABASE_NAME = "compliance_agent"
COLLECTION_NAME = "daily_usage"

_mongo_client = None


def _get_usage_collection():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(os.environ["MONGODB_URI"])
    return _mongo_client[DATABASE_NAME][COLLECTION_NAME]


def _today_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_remaining_today():
    """Returns how many of today's shared budget units are still available, without spending any."""
    collection = _get_usage_collection()
    doc = collection.find_one({"_id": _today_key()})
    used = doc["count"] if doc else 0
    return max(0, DAILY_LIMIT - used)


def try_use_budget(units):
    """
    Attempts to atomically reserve the given number of units from
    today's shared budget. Returns True and reserves them only if
    enough remain, or returns False and reserves nothing at all, so a
    single question (or a three system comparison, which needs three
    units) is never partially charged. This uses a single atomic
    database operation, so two visitors submitting a question at the
    same moment cannot both slip past the limit.
    """
    collection = _get_usage_collection()
    today = _today_key()

    # Make sure today's counter document exists, without touching its
    # value if it is already there.
    collection.update_one({"_id": today}, {"$setOnInsert": {"count": 0}}, upsert=True)

    result = collection.find_one_and_update(
        {"_id": today, "count": {"$lte": DAILY_LIMIT - units}},
        {"$inc": {"count": units}},
    )
    return result is not None
