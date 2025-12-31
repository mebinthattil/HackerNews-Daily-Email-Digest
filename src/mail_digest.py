import sys
import os
import requests
from datetime import datetime

# Add parent directory to path for `main` import. This is weird, but wanted to use the inbuilt render template to pass args, not sure how else to do it.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import render_template
from main import app
import digest_generator
from tools import _get_mailgun_config
from logger import setup_logger, log_section

logger = setup_logger(__name__)

# Path to archives directory (relative to project root)
ARCHIVES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'archives'))


def save_to_archive(html_content: str) -> bool:
    """save digest HTML to archives directory in DD-MM-YYYY.html format."""
    filename = datetime.now().strftime("%d-%m-%Y") + ".html"
    filepath = os.path.join(ARCHIVES_DIR, filename)
    
    try:
        os.makedirs(ARCHIVES_DIR, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(html_content)
        logger.info(f"Archived digest to: {filepath}")
        return True
    except IOError as e:
        logger.error(f"Failed to archive digest: {e}")
        return False


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
    log_section("Starting Digest Generation", logger)
    logger.info(f"Generating digest for top {story_count} stories...")
    
    digest_data = digest_generator.generate_digest(count=story_count)
    
    if not digest_data:
        logger.error("No digest data generated.")
        return
    
    log_section("Rendering Email Template", logger)
    logger.info(f"Rendering template for {len(digest_data)} stories...")
    
    with app.app_context():
        html_content = render_template(
            "digest.html",
            articles=list(digest_data.values()),
            date=datetime.now().strftime("%B %d, %Y"),
            unsubscribe_url="%mailing_list_unsubscribe_url%"
        )
    
    log_section("Saving to Archive", logger)
    if save_to_archive(html_content):
        logger.info("Digest archived successfully!")
    else:
        logger.warning("Failed to archive digest, continuing with email send...")
    
    log_section("Sending Email", logger)
    if send_digest_to_list(html_content):
        logger.info("Digest sent successfully!")
    else:
        logger.error("Failed to send digest.")


if __name__ == "__main__":
    main(story_count=2)
