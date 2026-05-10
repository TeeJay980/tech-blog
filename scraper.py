import feedparser
import json
import re
import os
import requests
from bs4 import BeautifulSoup
import sys
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask import Flask

import os

# Setup a minimal app for DB context
db_app = Flask(__name__)

# Priority: Cloud (Postgres) -> Local (SQLite)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///blog.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

db_app.config['SQLALCHEMY_DATABASE_URI'] = db_url
db_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(db_app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(500), unique=True)
    summary = db.Column(db.Text)
    excerpt = db.Column(db.String(300))
    content = db.Column(db.Text)
    image = db.Column(db.String(500))
    source = db.Column(db.String(100))
    category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_user_post = db.Column(db.Boolean, default=False)
    author_id = db.Column(db.Integer, nullable=True)
    likes_count = db.Column(db.Integer, default=0)
FEEDS = {
    "Tech": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss"
    ],
    "Politics": [
        "https://feeds.bbci.co.uk/news/politics/rss.xml",
        "https://www.politico.com/rss/politicopulse.xml"
    ],
    "Sports": [
        "https://www.espn.com/espn/rss/news",
        "https://feeds.bbci.co.uk/sport/rss.xml"
    ],
    "Lifestyle": [
        "https://www.theguardian.com/lifeandstyle/rss",
        "https://www.bbc.com/culture/feed.rss"
    ]
}

# Browser-like headers to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}

def clean_html(raw_html):
    """Remove html tags from a string."""
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def fetch_full_content_and_image(url):
    """Fetch the full article content and high-res image from the source URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None, None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Extract High-Res Image (Open Graph)
        featured_image = None
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            featured_image = og_image['content']
        else:
            twitter_image = soup.find('meta', name='twitter:image')
            if twitter_image and twitter_image.get('content'):
                featured_image = twitter_image['content']

        # 2. Extract Article Content - More aggressive selectors
        content_area = None
        selectors = [
            'article', 'main', 
            '[itemprop="articleBody"]', 
            '.article-body', '.article__body', '.article-content', 
            '.post-content', '.story-body', '.entry-content', 
            '.caas-body', '.js-article-body',
            '.duet--article--article-body',
            '.body-text', '.content-body',
            'div[class*="article-body"]',
            'div[class*="PostContent"]'
        ]
        
        for selector in selectors:
            content_area = soup.select_one(selector)
            if content_area:
                # Basic validation: does it contain enough paragraphs?
                if len(content_area.find_all('p')) >= 2:
                    break
        
        if not content_area:
            # Sophisticated Fallback: Find the tag with the most cumulative text in <p> tags
            best_div = None
            max_text = 0
            for div in soup.find_all(['div', 'section']):
                paragraphs = div.find_all('p', recursive=False)
                text_len = sum(len(p.get_text()) for p in paragraphs)
                if text_len > max_text:
                    max_text = text_len
                    best_div = div
            content_area = best_div

        article_html = ""
        if content_area:
            # Aggressive noise cleaning
            for noise in content_area.select('script, style, nav, aside, footer, header, iframe, .ad, .ads, .social-share, .related-links, .newsletter-signup, .inline-ad'):
                noise.decompose()
            
            # Extract paragraphs, but preserve some formatting (bold, links)
            paragraphs = content_area.find_all('p')
            if paragraphs:
                html_chunks = []
                for p in paragraphs:
                    text = p.get_text().strip()
                    if len(text) > 30: # Filter out short snippets
                        # Preserve internal links if they are short
                        html_chunks.append(f"<p style='margin-bottom: 1.5rem;'>{text}</p>")
                
                article_html = "".join(html_chunks)
        
        return article_html, featured_image
    except Exception as e:
        print(f"Error fetching content/image from {url}: {e}")
        return None, None

def extract_image(entry):
    """Attempt to find a featured image in the feed entry."""
    # 1. Try media:content
    if 'media_content' in entry and len(entry.media_content) > 0:
        content = entry.media_content[0]
        if 'url' in content:
            return content['url']
    
    # 2. Try media:thumbnail
    if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
        thumb = entry.media_thumbnail[0]
        if 'url' in thumb:
            return thumb['url']
    
    # 3. Try looking inside the summary/description for an <img> tag
    content = entry.get('summary', '') + entry.get('description', '')
    img_match = re.search(r'<img [^>]*src="([^"]+)"', content)
    if img_match:
        return img_match.group(1)
        
    # 4. Fallback to placeholder
    return "assets/placeholder.png"

def scrape():
    # Console fix
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    with db_app.app_context():
        db.create_all()
        
        for category, urls in FEEDS.items():
            print(f"--- Processing Category: {category} ---")
            category_posts = []
            
            for url in urls:
                print(f"Fetching: {url}")
                feed = feedparser.parse(url)
                source_name = feed.feed.get('title', 'Tech News')
                
                for entry in feed.entries:
                    category_posts.append({
                        "entry": entry,
                        "source": source_name,
                        "category": category
                    })

            # Sort category posts by date
            def get_date(item):
                e = item['entry']
                return e.get('published_parsed', None) or datetime.min

            category_posts.sort(key=get_date, reverse=True)

            # Process top 12 per category
            top_entries = category_posts[:12]

            for i, item in enumerate(top_entries):
                entry = item['entry']
                source = item['source']
                cat = item['category']
                link = entry.get('link', '#')
                
                # Skip if already in DB
                if Post.query.filter_by(link=link).first():
                    print(f"[{cat}] skipping (already in DB): {entry.get('title', 'Untitled')}")
                    continue

                print(f"[{cat}] [{i+1}/12] fetching deep content for: {entry.get('title', 'Untitled')}")
                
                full_content, web_image = fetch_full_content_and_image(link)
                summary_raw = entry.get('summary', '') or entry.get('description', '')
                rss_image = extract_image(entry)
                
                new_post = Post(
                    title=entry.get('title', 'Untitled'),
                    link=link,
                    summary=clean_html(summary_raw),
                    excerpt=clean_html(summary_raw[:160]) + "...",
                    content=full_content if full_content else clean_html(summary_raw),
                    image=web_image if web_image else rss_image,
                    source=source,
                    category=cat,
                    is_user_post=False
                )
                db.session.add(new_post)
                db.session.commit()

        print(f"\nSuccessfully synced total news to blog.db")

if __name__ == "__main__":
    scrape()

if __name__ == "__main__":
    scrape()
