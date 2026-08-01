"""Identify books using the Hardcover API."""
from calibre_plugins.hardcover_metadata.api import get_books
from calibre_plugins.hardcover_metadata.metadata import build_metadata
from calibre_plugins.hardcover_metadata.ranking import (
    rank_candidates, title_match_score, author_match_score
)
from calibre_plugins.hardcover_metadata.search import find_book_ids


def identify(plugin, log, result_queue, abort, title=None, authors=None,
             identifiers=None, timeout=30):
    """Main identify entry point. Finds books matching the query and
    queues Metadata results."""
    identifiers = identifiers or {}
    api_key = plugin.prefs.get('api_key', '')
    if not api_key:
        log.error('Hardcover API key not configured')
        return None

    # Resolve identifiers to candidate book IDs
    book_ids = find_book_ids(api_key, identifiers, title, authors,
                             log, abort, timeout)

    if abort.is_set():
        return None

    # Fetch full details in a single batch
    candidates = get_books(api_key, book_ids[:10], log, timeout)

    # Rank and filter
    if candidates:
        candidates = rank_candidates(candidates, title, authors)
        if title:
            candidates = [c for c in candidates
                          if title_match_score(c, title) >= 15]

        for c in candidates[:5]:
            a = author_match_score(c, authors) if authors else 0
            t = title_match_score(c, title) if title else 0
            pop = c.get('users_count', 0) or 0
            log('  Ranked: %s (author=%d, title=%d, users=%d)' %
                (c.get('slug', '?'), a, t, pop))

    # Build and queue metadata results
    for i, book_data in enumerate(candidates[:5]):
        mi = build_metadata(book_data, plugin, log)
        mi.source_relevance = i
        result_queue.put(mi)

    return None
