import hashlib
import logging
import os

from fetcher import fetch
from notifier import publish
from parser import parse
from state import get_last_hash, put_last_hash

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SITE_URL = os.environ["SITE_URL"]
SITE_NAME = os.environ["SITE_NAME"]
SCRAPE_TYPE = os.environ["SCRAPE_TYPE"]
CSS_SELECTOR = os.environ["CSS_SELECTOR"]
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "5"))
SSM_STATE_KEY = os.environ["SSM_STATE_KEY"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
NOTIFICATION_PREFIX = os.environ.get("NOTIFICATION_PREFIX", SITE_NAME)


def lambda_handler(event, context):
    logger.info(f"Scraping {SITE_NAME} — {SITE_URL}")

    html = fetch(SITE_URL)
    items = parse(html, SCRAPE_TYPE, CSS_SELECTOR, MAX_ITEMS)

    if not items:
        logger.warning(f"No items parsed — first 500 chars of response: {html[:500]!r}")
        return {"status": "no_items"}

    content_hash = hashlib.sha256("\n".join(items).encode()).hexdigest()
    last_hash = get_last_hash(SSM_STATE_KEY)

    if content_hash == last_hash:
        logger.info("No change detected")
        return {"status": "no_change"}

    logger.info("New content detected — notifying")

    # Truncate to keep SMS under segment limits
    first_item = items[0][:300]
    message = f"{NOTIFICATION_PREFIX}:\n\n{first_item}\n\n{SITE_URL}"

    publish(SNS_TOPIC_ARN, message, subject=SITE_NAME)
    put_last_hash(SSM_STATE_KEY, content_hash)

    return {"status": "notified", "hash": content_hash}
