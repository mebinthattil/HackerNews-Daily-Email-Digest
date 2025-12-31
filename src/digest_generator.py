import requests 
from typing import List
import scrape
import summarize
from logger import setup_logger, log_section, log_progress

logger = setup_logger(__name__)


def top_stories(count = 10) -> List[int]:
    res = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json')
    top_stories: List[int] = res.json()[:count]
    return top_stories


def get_story_data(item_id: int) -> dict:
    res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json')
    return res.json()


def get_post_summary(story_data: dict) -> str:
    url = story_data.get('url', '')
    if not url:
        return None
    scraped_contents = scrape.scrape_site(url)
    if scraped_contents is not None:
        return summarize.summarize(scraped_contents, prompt_mode="post")
    return None


def get_comment_summaries(comment_ids: List[int]) -> str:
    all_comments_text = ""
    for comment_id in comment_ids:
        res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{comment_id}.json')
        comment_data = res.json()
        if comment_data and 'text' in comment_data:
            all_comments_text += comment_data['text'] + "\n"
    if all_comments_text:
        return summarize.summarize(all_comments_text, prompt_mode="comments")
    return None


def get_comments_url(item_id: int) -> str:
    return f"https://news.ycombinator.com/item?id={item_id}"


def generate_digest(count = 10) -> dict:
    log_section("Fetching Stories", logger)
    story_ids = top_stories(count)
    logger.info(f"Found {len(story_ids)} top stories")
    
    digest_data = {}
    total = len(story_ids)
    
    for idx, story_id in enumerate(story_ids, 1):
        story_data = get_story_data(story_id)
        title = story_data.get('title', 'No Title')
        
        log_progress(idx, total, f"Processing: {title[:50]}{'...' if len(title) > 50 else ''}", logger)
        
        log_section(f"Scraping [{idx}/{total}]", logger)
        summary = get_post_summary(story_data)
        
        comment_ids = story_data.get('kids', [])
        log_section(f"Summarizing Comments [{idx}/{total}]", logger)
        logger.info(f"Processing {len(comment_ids)} comments")
        comment_summary = get_comment_summaries(comment_ids)
        
        digest_data[story_id] = {
            "title": title,
            "url": story_data.get('url', ''),
            "comments_url": get_comments_url(story_id),
            "points": story_data.get('score', 0),
            "author": story_data.get('by', 'unknown'),
            "comments_count": len(comment_ids),
            "post_summary": summary,
            "comment_summary": comment_summary,
        }
        
        logger.info(f"Completed story {idx}/{total}\n")
    
    log_section("Digest Complete", logger)
    logger.info(f"Generated digest for {len(digest_data)} stories")
    
    return digest_data