"""Resolve book identifiers to a Hardcover book ID."""
from calibre.ebooks.metadata import check_isbn

from calibre_plugins.hardcover_metadata.api import (
    search_books, get_edition_by_isbn
)


def find_book_ids(api_key, identifiers, title, authors, log, abort, timeout=30):
    """Resolve identifiers/title/authors into a list of candidate book IDs.

    Tries in order: hardcover-id, ISBN, hardcover slug, title search.
    """
    book_ids = []

    # Direct numeric book ID
    hardcover_book_id = identifiers.get('hardcover-id')
    if hardcover_book_id:
        try:
            book_ids.append(int(hardcover_book_id))
        except (ValueError, TypeError):
            pass

    # ISBN lookup
    if not book_ids:
        isbn = identifiers.get('isbn')
        if isbn and check_isbn(isbn):
            edition = get_edition_by_isbn(api_key, isbn, log, timeout)
            if edition:
                bid = edition.get('book_id') or edition.get('book', {}).get('id')
                if bid:
                    book_ids.append(bid)

    # Hardcover slug search
    if not book_ids:
        slug = identifiers.get('hardcover') or identifiers.get('hardcover-slug')
        if slug:
            found = search_books(api_key, slug.replace('-', ' '), log, timeout)
            for bid in found:
                if bid not in book_ids:
                    book_ids.append(bid)

    # Title search
    if not book_ids and title:
        if abort and abort.is_set():
            return book_ids
        found = search_books(api_key, title, log, timeout)
        for bid in found:
            if bid not in book_ids:
                book_ids.append(bid)

    # Title + author fallback
    if not book_ids and title and authors:
        if abort and abort.is_set():
            return book_ids
        query = '%s %s' % (title, ' '.join(authors))
        found = search_books(api_key, query, log, timeout)
        for bid in found:
            if bid not in book_ids:
                book_ids.append(bid)

    return book_ids
