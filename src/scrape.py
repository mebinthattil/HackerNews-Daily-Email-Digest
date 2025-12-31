# This file is vibecoded, hopefully this does not break
# TODO: Write better code for this
from typing import Optional
import re
import logging
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO)

def scrape_site(url: str) -> Optional[str]:
    """
    Scrape a website and extract its main content, including text and image alt tags.
    
    Args:
        url: The URL of the website to scrape
        
    Returns:
        str: Extracted text content suitable for LLM processing, or None if scraping failed
        
    Features:
        - Extracts main article/content body
        - Includes image alt text and captions
        - Handles various HTML structures
        - Bypasses common anti-scraping measures
        - Skips paywalled content gracefully
        - Uses multiple fallback strategies
    """
    try:
        # Import required libraries
        try:
            import requests
            from bs4 import BeautifulSoup
            from readability import Document
        except ImportError as e:
            missing_lib = str(e).split("'")[1] if "'" in str(e) else "unknown"
            logger.error(f"Missing required library: {missing_lib}. Install with: pip install requests beautifulsoup4 readability-lxml")
            return None
        
        # Set up headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.error(f"Invalid URL: {url}")
            return None
        
        # Check if URL points to a PDF
        if parsed.path.lower().endswith('.pdf'):
            logger.info(f"Skipping PDF file: {url}")
            return None
        
        # Make request with timeout
        logger.info(f"Scraping URL: {url}")
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        # Check Content-Type header for PDF
        content_type = response.headers.get('Content-Type', '').lower()
        if 'application/pdf' in content_type or 'pdf' in content_type:
            logger.info(f"Skipping PDF content type: {url}")
            return None
        
        # Check for common paywall indicators in status code or redirects
        if response.status_code == 402:  # Payment Required
            logger.info(f"Paywall detected (402): {url}")
            return None
            
        # Get the HTML content
        html_content = response.text
        
        # Check for common paywall indicators in HTML
        paywall_indicators = [
            'paywall', 'subscription required', 'subscribe to read',
            'premium content', 'member-only', 'subscribers only'
        ]
        lower_html = html_content.lower()
        if any(indicator in lower_html for indicator in paywall_indicators):
            # Check if it's a hard paywall (most content hidden)
            soup = BeautifulSoup(html_content, 'html.parser')
            text_length = len(soup.get_text().strip())
            if text_length < 500:  # Likely a hard paywall
                logger.info(f"Paywall detected in content: {url}")
                return None
        
        # Use readability to extract main content
        doc = Document(html_content)
        title = doc.title()
        
        # Parse the cleaned HTML from readability
        readable_html = doc.summary()
        soup = BeautifulSoup(readable_html, 'html.parser')
        
        # Also parse the original HTML for fallback
        original_soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        unwanted_tags = ['script', 'style', 'nav', 'header', 'footer', 'aside', 
                        'advertisement', 'ad', 'sidebar', 'menu', 'iframe',
                        'noscript', 'form', 'button']
        
        for tag_name in unwanted_tags:
            for element in soup.find_all(tag_name):
                element.decompose()
                
        # Remove elements with common ad/navigation classes
        unwanted_classes = ['advertisement', 'ad-container', 'social-share', 
                           'comments', 'related-posts', 'newsletter-signup',
                           'popup', 'modal', 'cookie-banner']
        
        for class_name in unwanted_classes:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                element.decompose()
        
        # Extract text content
        content_parts = []
        
        # Add title
        if title:
            content_parts.append(f"Title: {title}\n")
            content_parts.append("=" * 80 + "\n")
        
        # Extract main text content with structure
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'blockquote', 'pre', 'code']):
            text = element.get_text(strip=True)
            if text:
                # Add formatting based on element type
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    level = int(element.name[1])
                    content_parts.append(f"\n{'#' * level} {text}\n")
                elif element.name == 'blockquote':
                    content_parts.append(f"\n> {text}\n")
                elif element.name == 'li':
                    content_parts.append(f"• {text}\n")
                else:
                    content_parts.append(f"{text}\n")
        
        # Extract image information (alt text, captions, titles)
        images_info = []
        
        # Try to find images in the cleaned content first
        for img in soup.find_all('img'):
            img_data = {}
            
            if img.get('alt'):
                img_data['alt'] = img['alt'].strip()
            if img.get('title'):
                img_data['title'] = img['title'].strip()
            if img.get('src'):
                img_data['src'] = urljoin(url, img['src'])
            
            # Look for captions near the image
            parent = img.parent
            if parent:
                # Check for figcaption
                figcaption = parent.find('figcaption')
                if figcaption:
                    img_data['caption'] = figcaption.get_text(strip=True)
                # Check for caption class
                caption_elem = parent.find(class_=re.compile(r'caption', re.I))
                if caption_elem and 'caption' not in img_data:
                    img_data['caption'] = caption_elem.get_text(strip=True)
            
            if img_data:
                images_info.append(img_data)
        
        # Fallback: also check original HTML if we didn't find many images
        if len(images_info) < 3:
            for img in original_soup.find_all('img'):
                # Only add if we haven't seen this image already
                alt = img.get('alt', '').strip()
                if alt and not any(i.get('alt') == alt for i in images_info):
                    img_data = {'alt': alt}
                    if img.get('title'):
                        img_data['title'] = img['title'].strip()
                    images_info.append(img_data)
        
        # Add image information to content
        if images_info:
            content_parts.append("\n" + "=" * 80 + "\n")
            content_parts.append("Images and Visual Content:\n")
            content_parts.append("=" * 80 + "\n")
            
            for idx, img_data in enumerate(images_info, 1):
                content_parts.append(f"\nImage {idx}:\n")
                if 'alt' in img_data:
                    content_parts.append(f"  Alt text: {img_data['alt']}\n")
                if 'title' in img_data:
                    content_parts.append(f"  Title: {img_data['title']}\n")
                if 'caption' in img_data:
                    content_parts.append(f"  Caption: {img_data['caption']}\n")
        
        # Combine all parts
        full_content = ''.join(content_parts).strip()
        
        # Validate we got meaningful content
        if len(full_content) < 100:
            logger.warning(f"Extracted content is too short ({len(full_content)} chars): {url}")
            # Try a simpler extraction as fallback
            full_content = _simple_text_extract(original_soup, title, url)
            
            if len(full_content) < 100:
                logger.error(f"Failed to extract meaningful content: {url}")
                return None
        
        # Clean up excessive whitespace
        full_content = re.sub(r'\n{3,}', '\n\n', full_content)
        full_content = re.sub(r' {2,}', ' ', full_content)
        
        logger.info(f"Successfully scraped {len(full_content)} characters from: {url}")
        return full_content
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout while scraping: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while scraping {url}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while scraping {url}: {str(e)}")
        return None


def _simple_text_extract(soup, title: str, url: str) -> str:
    """
    Fallback method for extracting text when readability doesn't work well.
    
    Args:
        soup: BeautifulSoup object of the page
        title: Page title
        url: Original URL
        
    Returns:
        str: Extracted text content
    """
    logger.info(f"Using simple text extraction fallback for: {url}")
    
    # Remove unwanted elements
    for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
        element.decompose()
    
    content_parts = []
    
    if title:
        content_parts.append(f"Title: {title}\n")
        content_parts.append("=" * 80 + "\n")
    
    # Try to find main content area
    main_content = None
    
    # Look for common content containers
    for selector in [
        {'id': re.compile(r'(main|content|article|post|entry)', re.I)},
        {'class': re.compile(r'(main|content|article|post|entry|body)', re.I)},
        {'role': 'main'},
    ]:
        main_content = soup.find(['main', 'article', 'div', 'section'], selector)
        if main_content:
            break
    
    # If no main content found, use body
    if not main_content:
        main_content = soup.find('body')
    
    if main_content:
        # Get all text
        text = main_content.get_text(separator='\n', strip=True)
        content_parts.append(text)
    else:
        # Last resort: get all text from soup
        text = soup.get_text(separator='\n', strip=True)
        content_parts.append(text)
    
    full_content = '\n'.join(content_parts)
    
    # Clean up
    full_content = re.sub(r'\n{3,}', '\n\n', full_content)
    full_content = re.sub(r' {2,}', ' ', full_content)
    
    return full_content.strip()
