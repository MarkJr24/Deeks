import re
import urllib.parse
import webbrowser
from logger import logger

# Common site mappings (friendly name -> URL)
# Designed to be easily extensible with additional sites
SITE_MAP = {
    "youtube": "https://www.youtube.com",
    "spotify": "https://open.spotify.com",
    "gmail": "https://mail.google.com",
    "google mail": "https://mail.google.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
}

_URL_PATTERN = re.compile(
    r'^(?:https?://)?(?:www\.)?'
    r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
    r'(?::\d+)?(?:/[^\s]*)?$',
    re.IGNORECASE,
)


def is_probable_url(text: str) -> bool:
    """Checks if the given text looks like a raw URL or domain name."""
    if not text:
        return False
    candidate = text.strip()
    return bool(_URL_PATTERN.match(candidate))


def is_known_site(site_name: str) -> bool:
    """Checks whether the normalized site name exists in SITE_MAP."""
    if not site_name:
        return False
    clean = _normalize_site_name(site_name)
    return clean in SITE_MAP


def _normalize_site_name(name: str) -> str:
    """Normalizes spoken site name by stripping whitespace, punctuation, and common filler words."""
    clean = name.lower().strip().strip('."\'')
    clean = re.sub(r'^(?:the\s+)', '', clean)
    clean = re.sub(r'\s+(?:website|site|dot\s+com|dot\s+org|dot\s+net)$', '', clean).strip()
    return clean


def search_web(query: str) -> str:
    """
    Opens the default browser to a Google search results page for the given query.
    Returns a spoken confirmation message: 'Searching the web for [query].'
    """
    clean_query = query.strip() if query else ""
    if not clean_query:
        logger.debug("search_web called with empty query.")
        return "What would you like me to search for?"

    encoded_query = urllib.parse.quote_plus(clean_query)
    search_url = f"https://www.google.com/search?q={encoded_query}"

    logger.debug(f"Opening Google search for query '{clean_query}': {search_url}")
    try:
        webbrowser.open(search_url)
    except Exception as e:
        logger.exception(f"Error opening browser for search query '{clean_query}': {e}")
        return "I encountered an error trying to search the web."

    return f"Searching the web for {clean_query}."


def open_site(site_name: str) -> str:
    """
    Opens a website by name from SITE_MAP, or falls back to treating it as a raw URL.
    If not recognized and not a URL, returns 'I don't know that site yet.'
    """
    raw_name = site_name.strip() if site_name else ""
    if not raw_name:
        logger.debug("open_site called with empty site_name.")
        return "Which site would you like me to open?"

    clean_key = _normalize_site_name(raw_name)

    # 1. Check mapped friendly names
    if clean_key in SITE_MAP:
        url = SITE_MAP[clean_key]
        logger.debug(f"Resolved site '{raw_name}' via SITE_MAP -> {url}")
        try:
            webbrowser.open(url)
            return f"Opening {raw_name}."
        except Exception as e:
            logger.exception(f"Error opening browser for mapped site '{raw_name}': {e}")
            return f"I encountered an error trying to open {raw_name}."

    # 2. Fall back to treating it as a raw URL if it looks like one
    candidate = raw_name.strip().replace(" ", "")
    if is_probable_url(candidate):
        target_url = candidate
        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = f"https://{target_url}"

        logger.debug(f"Treating unrecognized site '{raw_name}' as raw URL -> {target_url}")
        try:
            webbrowser.open(target_url)
            return f"Opening {raw_name}."
        except Exception as e:
            logger.exception(f"Error opening browser for raw URL '{target_url}': {e}")
            return f"I encountered an error trying to open {raw_name}."

    # 3. Not recognized
    logger.debug(f"Site name '{raw_name}' is not recognized and is not a valid URL.")
    return "I don't know that site yet."

# Compatibility aliases
open_website = open_site
perform_search = search_web

