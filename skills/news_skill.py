import html
import urllib.request
import xml.etree.ElementTree as ET
from logger import logger

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
]

def clean_headline(title: str) -> str:
    """Cleans up raw RSS title text for natural text-to-speech output."""
    if not title:
        return ""
    # Unescape HTML entities
    title = html.unescape(title.strip())
    # Remove common channel suffixes like " - BBC News" or " - CNN"
    if " - BBC News" in title:
        title = title.replace(" - BBC News", "")
    elif " - BBC" in title:
        title = title.replace(" - BBC", "")
    return title.strip()

def get_top_headlines(limit: int = 4) -> dict:
    """
    Fetches the top news headlines using a free RSS feed.
    Returns a dict with success status, list of headlines, and spoken summary.
    """
    headlines = []
    
    for feed_url in RSS_FEEDS:
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DeeksVoiceAssistant/1.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                xml_data = response.read()
                
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            
            for item in items:
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    cleaned = clean_headline(title_elem.text)
                    if cleaned and cleaned not in headlines:
                        headlines.append(cleaned)
                    if len(headlines) >= limit:
                        break
                        
            if headlines:
                break
        except Exception as e:
            logger.warning(f"Failed to fetch RSS from '{feed_url}': {e}")
            continue

    if not headlines:
        logger.error("Could not fetch headlines from any RSS source.")
        return {
            "success": False,
            "headlines": [],
            "summary": "I'm having trouble fetching the latest news right now."
        }

    # Format speech-friendly summary
    # e.g., "Here are today's top headlines. First: ... Second: ... Third: ... Fourth: ..."
    ordinal_words = ["First", "Second", "Third", "Fourth", "Fifth"]
    spoken_parts = []
    for i, h in enumerate(headlines[:limit]):
        prefix = ordinal_words[i] if i < len(ordinal_words) else f"Number {i+1}"
        spoken_parts.append(f"{prefix}: {h}")
        
    summary = "Here are the top headlines. " + ". ".join(spoken_parts) + "."
    
    return {
        "success": True,
        "headlines": headlines,
        "summary": summary
    }
