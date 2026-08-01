"""Download cover art from Hardcover."""
from calibre_plugins.hardcover_metadata.api import get_book_cover
from calibre_plugins.hardcover_metadata.metadata import extract_cover_url
from calibre_plugins.hardcover_metadata.search import find_book_ids


def download_cover(plugin, log, result_queue, abort, title=None, authors=None,
                   identifiers=None, timeout=30, get_best_cover=False):
    """Download the book's cover from the most popular edition in the
    preferred language."""
    identifiers = identifiers or {}
    api_key = plugin.prefs.get('api_key', '')
    if not api_key:
        log.error('Hardcover API key not configured')
        return None

    # Find the book
    book_ids = find_book_ids(api_key, identifiers, title, authors,
                             log, abort, timeout)
    if not book_ids:
        return None

    book_id = book_ids[0]
    preferred_language = plugin.prefs.get('preferred_language', 'English')

    # Fetch the best edition cover in preferred language
    book_data = get_book_cover(api_key, book_id, preferred_language, log, timeout)
    if not book_data:
        return None

    # Use the top edition's cover, fall back to book-level cover
    cover_url = None
    editions = book_data.get('editions', [])
    if editions:
        cover_url = extract_cover_url(editions[0].get('cached_image'))
    if not cover_url:
        cover_url = extract_cover_url(book_data.get('cached_image'))

    if not cover_url:
        log.error('No cover URL found for book')
        return None

    log('Downloading Hardcover cover: %s' % cover_url)

    from calibre import browser
    br = browser()

    try:
        response = br.open_novisit(cover_url, timeout=timeout)
        cover_data = response.read()
        if cover_data:
            result_queue.put((plugin, cover_data))
    except Exception as e:
        log.error('Failed to download book cover: %s' % str(e))

    return None
