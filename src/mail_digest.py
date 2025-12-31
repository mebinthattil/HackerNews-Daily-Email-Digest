import sys
import os
import logging
import requests
from datetime import datetime

# Add parent directory to path for `main` import. This is weird, but wanted to use the inbuilt render template to pass args, not sure how else to do it.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import render_template
from main import app
import digest_generator
from tools import _get_mailgun_config

logger = logging.getLogger(__name__)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO)


def send_digest_to_list(html_content: str) -> bool:
    """Send digest email to the mailing list."""
    api_key, list_name, domain_name, err = _get_mailgun_config()
    
    if err:
        logger.error(err)
        return False
    
    from_addr = f"{list_name}@{domain_name}"
    to_addr = f"{list_name}@{domain_name}"
    url = f"https://api.mailgun.net/v3/{domain_name}/messages"
    
    subject = f"HackerNews Digest - {datetime.now().strftime('%B %d, %Y')}"
    text = f"{subject}\n\nView this email in HTML to see the full digest."
    
    data = {
        "from": from_addr,
        "to": to_addr,
        "subject": subject,
        "text": text,
        "html": html_content,
    }
    
    try:
        response = requests.post(url, auth=("api", api_key), data=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Digest sent to mailing list: {to_addr}")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send digest: {e}")
        return False


def main(story_count: int = 10):
    """Generate and send digest."""
    logger.info(f"Generating digest for top {story_count} stories...")
    
    digest_data = digest_generator.generate_digest(count=story_count)
    
    if not digest_data:
        logger.error("No digest data generated.")
        return
    
    logger.info(f"Sending digest for {len(digest_data)} stories...")
    
    with app.app_context():
        html_content = render_template(
            "digest.html",
            articles=list(digest_data.values()),
            date=datetime.now().strftime("%B %d, %Y"),
            unsubscribe_url="%mailing_list_unsubscribe_url%"
        )
    
    if send_digest_to_list(html_content):
        logger.info("Digest sent successfully!")
    else:
        logger.error("Failed to send digest.")


if __name__ == "__main__":
    main(story_count=2)
