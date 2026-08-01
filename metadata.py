"""Build Calibre Metadata objects from Hardcover API data."""
import json
from datetime import datetime

from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata


# reading_format_id: 1=Physical, 2=Audio, 3=Both, 4=Ebook
EDITION_FORMAT_MAP = {
    'ebook': 4,
    'physical': 1,
    'audiobook': 2,
}


def build_metadata(book_data, plugin, log):
    """Convert Hardcover book data into a Calibre Metadata object."""
    title = book_data.get('title', '')
    authors = _extract_authors(book_data)
    mi = Metadata(title, authors)

    slug = book_data.get('slug', '')
    if slug:
        mi.set_identifier('hardcover', slug)

    _set_rating(mi, book_data)
    _set_comments(mi, book_data)
    _set_series(mi, book_data)
    _set_tags(mi, book_data, plugin.prefs.get('genre_mappings', {}), log)
    _set_edition_data(mi, book_data, plugin.prefs)
    _set_pubdate(mi, book_data, plugin.prefs)
    _set_cover(mi, book_data, plugin, slug)

    mi.source_relevance = 0
    return mi


def select_preferred_edition(editions, preferred_format):
    """Pick the best edition: prefer matching format with ISBN."""
    format_id = EDITION_FORMAT_MAP.get(preferred_format, 4)

    # Preferred format with ISBN
    for ed in editions:
        if ed.get('reading_format_id') == format_id:
            if ed.get('isbn_13') or ed.get('isbn_10'):
                return ed

    # Preferred format without ISBN
    for ed in editions:
        if ed.get('reading_format_id') == format_id:
            return ed

    # Any edition with ISBN
    for ed in editions:
        if ed.get('isbn_13') or ed.get('isbn_10'):
            return ed

    return editions[0] if editions else None


def map_genres(cached_tags, genre_mappings, log, min_count=2):
    """Map Hardcover genre tags to Calibre tags.

    Mapped genres are always included (whitelist).
    Unmapped genres require count >= min_count.
    """
    if not cached_tags:
        return []

    if isinstance(cached_tags, str):
        try:
            cached_tags = json.loads(cached_tags)
        except (json.JSONDecodeError, TypeError):
            return []

    if not isinstance(cached_tags, dict):
        return []

    tags = []
    for item in cached_tags.get('Genre', []):
        if not isinstance(item, dict):
            continue
        name = item.get('tag')
        count = item.get('count', 0)
        if not name:
            continue

        if name in genre_mappings:
            mapped = genre_mappings[name]
            if mapped:  # Empty mapping = exclude
                tags.append(mapped)
        elif count >= min_count:
            tags.append(name)

    return tags


def extract_cover_url(cached_image):
    """Extract URL from a cached_image field (dict or JSON string)."""
    if not cached_image:
        return None
    if isinstance(cached_image, str):
        try:
            cached_image = json.loads(cached_image)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(cached_image, dict):
        return cached_image.get('url')
    return None


def parse_date(date_str):
    """Parse a date string (YYYY-MM-DD or YYYY) into a datetime."""
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%Y'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


# --- Private helpers ---

def _extract_authors(book_data):
    """Extract primary authors (role is null or 'Author')."""
    authors = []
    for contrib in book_data.get('contributions', []):
        role = contrib.get('contribution')
        if role is None or role == 'Author':
            name = contrib.get('author', {}).get('name')
            if name:
                authors.append(name)
    return authors or ['Unknown']


def _set_rating(mi, book_data):
    rating = book_data.get('rating')
    if rating is not None:
        try:
            mi.rating = float(rating) * 2  # Hardcover 0-5 → Calibre 0-10
        except (ValueError, TypeError):
            pass


def _set_comments(mi, book_data):
    headline = book_data.get('headline')
    description = book_data.get('description')
    if headline and description:
        mi.comments = '%s\n\n%s' % (headline, description)
    elif headline:
        mi.comments = headline
    elif description:
        mi.comments = description


def _set_series(mi, book_data):
    book_series = book_data.get('book_series', [])
    if not book_series:
        return
    primary = book_series[0]
    name = primary.get('series', {}).get('name')
    if name:
        mi.series = name
        pos = primary.get('position')
        if pos is not None:
            try:
                mi.series_index = float(pos)
            except (ValueError, TypeError):
                pass


def _set_tags(mi, book_data, genre_mappings, log):
    tags = map_genres(book_data.get('cached_tags'), genre_mappings, log)
    if tags:
        mi.tags = tags


def _set_edition_data(mi, book_data, prefs):
    editions = book_data.get('editions', [])
    edition = select_preferred_edition(editions, prefs.get('preferred_edition', 'ebook'))
    if not edition:
        return

    # ISBN
    isbn_13 = edition.get('isbn_13')
    isbn_10 = edition.get('isbn_10')
    if isbn_13 and check_isbn(isbn_13):
        mi.set_identifier('isbn', isbn_13)
    elif isbn_10 and check_isbn(isbn_10):
        mi.set_identifier('isbn', isbn_10)

    # Publisher
    pub_name = (edition.get('publisher') or {}).get('name')
    if pub_name:
        mi.publisher = pub_name

    # Language
    lang_name = (edition.get('language') or {}).get('language')
    if lang_name:
        from calibre.utils.localization import canonicalize_lang
        canon = canonicalize_lang(lang_name)
        if canon:
            mi.languages = [canon]


def _set_pubdate(mi, book_data, prefs):
    edition = None
    editions = book_data.get('editions', [])
    if editions:
        edition = select_preferred_edition(editions, prefs.get('preferred_edition', 'ebook'))

    if prefs.get('use_original_pub_date', True):
        pub_date = parse_date(book_data.get('release_date'))
    else:
        pub_date = parse_date(edition.get('release_date')) if edition else None
        if not pub_date:
            pub_date = parse_date(book_data.get('release_date'))

    if pub_date:
        mi.pubdate = pub_date


def _set_cover(mi, book_data, plugin, slug):
    cover_url = extract_cover_url(book_data.get('cached_image'))
    if cover_url:
        mi.has_cover = True
        if slug:
            plugin.cache_identifier_to_cover_url(slug, cover_url)
