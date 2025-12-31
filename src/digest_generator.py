import requests 
from typing import List
import scrape
import summarize

def top_stories(count = 10) -> List[int]:
    res = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json')
    top_stories: List[int] = res.json()[:count]
    return top_stories

def get_post_summary(item_id: int) -> str:
    res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json')
    story_data = res.json()
    scraped_contents = scrape.scrape_site(story_data.get('url', ''))
    if scraped_contents is not None:
        return summarize.summarize(scraped_contents, prompt_mode="post")
    return None

def get_post_comment_ids(post_id: int) -> List[int]:
    res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{post_id}.json')
    post_data = res.json()
    return post_data.get('kids', [])

def get_comment_summaries(comment_ids: List[int]) -> str:
    all_comments_text = ""
    for comment_id in comment_ids:
        res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{comment_id}.json')
        comment_data = res.json()
        if comment_data and 'text' in comment_data: # we are not going to feed comments of comments for time being
            all_comments_text += comment_data['text'] + "\n"
    if all_comments_text:
        return summarize.summarize(all_comments_text, prompt_mode="comments")
    return None

def get_post_title(item_id: int) -> str:
    res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json')
    story_data = res.json()
    return story_data.get('title', 'No Title')

def get_post_score(item_id: int) -> int: #score is basically upvotes
    res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json')
    story_data = res.json()
    return story_data.get('score', 0)

def get_post_author(item_id: int) -> str:
    res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json')
    story_data = res.json()
    return story_data.get('by', 'unknown')

def get_post_url(item_id: int) -> str:
    res = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json')
    story_data = res.json()
    return story_data.get('url', '')

def get_comments_url(item_id: int) -> str:
    return f"https://news.ycombinator.com/item?id={item_id}"

def generate_digest(count = 10) -> dict:

    digest_data = {}
    for story_id in top_stories(count):
        summary = get_post_summary(story_id)
        comment_ids = get_post_comment_ids(story_id)
        comment_summary = get_comment_summaries(comment_ids)
        digest_data[story_id] = {
            "title": get_post_title(story_id),
            "url": get_post_url(story_id),
            "comments_url": get_comments_url(story_id),
            "points": get_post_score(story_id),
            "author": get_post_author(story_id),
            "comments_count": len(comment_ids),
            "post_summary": summary,
            "comment_summary": comment_summary,
        }
    return digest_data