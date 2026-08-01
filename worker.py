import json
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata


HARDCOVER_API_URL = 'https://api.hardcover.app/v1/graphql'

# reading_format_id: 1=Physical, 2=Audio, 3=Both, 4=Ebook
EDITION_FORMAT_MAP = {
    'ebook': 4,
    'physical': 1,
    'audiobook': 2,
}


def _graphql_request(api_key, query, variables=None, timeout=30):
    payload = {'query': query}
    if variables:
        payload['variables'] = variables

    data = json.dumps(payload).encode('utf-8')
    req = Request(HARDCOVER_API_URL, data=data)
    req.add_header('Content-Type', 'application/json')
    req.add_header('authorization', api_key)
    req.add_header('User-Agent', 'calibre-hardcover-metadata-plugin/1.0')

    response = urlopen(req, timeout=timeout)
    return json.loads(response.read().decode('utf-8'))


def _search_books(api_key, query, log, timeout=30):
    """Search for books using the Hardcover search API. Returns list of book IDs."""
    gql = '''
    query SearchBooks($query: String!) {
        search(query: $query, query_type: "Book", per_page: 10, page: 1) {
            ids
        }
    }
    '''
    try:
        result = _graphql_request(api_key, gql, {'query': query}, timeout)
        if 'errors' in result:
            log.error('Hardcover search error:', result['errors'])
            return []
        search_data = result.get('data', {}).get('search', {})
        ids = search_data.get('ids', [])
        if isinstance(ids, str):
            ids = json.loads(ids)
        # Ensure all IDs are integers
        return [int(i) for i in ids if i]
    except (HTTPError, URLError) as e:
        log.error('Hardcover API request failed:', str(e))
        return []
    except (ValueError, TypeError) as e:
        log.error('Hardcover search parse error:', str(e))
        return []


def _get_book_by_id(api_key, book_id, log, timeout=30):
    """Get full book details by ID."""
    results = _get_books_by_ids(api_key, [book_id], log, timeout)
    return results[0] if results else None


def _get_books_by_ids(api_key, book_ids, log, timeout=30):
    """Get full book details for multiple IDs in a single request."""
    if not book_ids:
        return []
    gql = '''
    query GetBooks($ids: [Int!]!) {
        books(where: {id: {_in: $ids}}) {
            id
            title
            subtitle
            slug
            headline
            description
            rating
            ratings_count
            users_count
            release_date
            release_year
            pages
            cached_image
            cached_tags
            contributions {
                author {
                    name
                }
                contribution
            }
            book_series {
                series {
                    name
                }
                position
            }
            editions {
                id
                title
                isbn_10
                isbn_13
                asin
                pages
                release_date
                reading_format_id
                edition_format
                cached_image
                language {
                    language
                }
                publisher {
                    name
                }
            }
        }
    }
    '''
    try:
        result = _graphql_request(api_key, gql, {'ids': book_ids}, timeout)
        if 'errors' in result:
            log.error('Hardcover book detail error:', result['errors'])
            return []
        return result.get('data', {}).get('books', [])
    except (HTTPError, URLError) as e:
        log.error('Hardcover API request failed:', str(e))
        return []


def _get_book_covers(api_key, book_id, log, timeout=30):
    """Get book and edition cover images only (lightweight query).
    Excludes audiobook editions (reading_format_id=2) since their covers
    are typically different artwork."""
    gql = '''
    query GetBookCovers($id: Int!) {
        books(where: {id: {_eq: $id}}) {
            id
            cached_image
            editions(
                where: {reading_format_id: {_nin: [2]}}
                order_by: {users_count: desc}
            ) {
                id
                cached_image
            }
        }
    }
    '''
    try:
        result = _graphql_request(api_key, gql, {'id': book_id}, timeout)
        if 'errors' in result:
            log.error('Hardcover cover query error:', result['errors'])
            return None
        books = result.get('data', {}).get('books', [])
        return books[0] if books else None
    except (HTTPError, URLError) as e:
        log.error('Hardcover API request failed:', str(e))
        return None


def _get_edition_by_isbn(api_key, isbn, log, timeout=30):
    """Look up an edition directly by ISBN."""
    field = 'isbn_13' if len(isbn) == 13 else 'isbn_10'
    gql = '''
    query GetEdition($isbn: String!) {
        editions(where: {%s: {_eq: $isbn}}) {
            id
            book_id
            book {
                id
                title
                slug
            }
        }
    }
    ''' % field
    try:
        result = _graphql_request(api_key, gql, {'isbn': isbn}, timeout)
        if 'errors' in result:
            return None
        editions = result.get('data', {}).get('editions', [])
        return editions[0] if editions else None
    except (HTTPError, URLError):
        return None


def _select_preferred_edition(editions, preferred_format):
    """Select the best edition based on user preference."""
    format_id = EDITION_FORMAT_MAP.get(preferred_format, 4)

    # First try to find an edition matching the preferred format AND has an ISBN
    for ed in editions:
        if ed.get('reading_format_id') == format_id:
            if ed.get('isbn_13') or ed.get('isbn_10'):
                return ed

    # Fall back to any edition matching the preferred format (even without ISBN)
    for ed in editions:
        if ed.get('reading_format_id') == format_id:
            return ed

    # Fall back to any edition with an ISBN
    for ed in editions:
        if ed.get('isbn_13') or ed.get('isbn_10'):
            return ed

    # Fall back to first edition
    return editions[0] if editions else None


def _normalize_author(name):
    """Normalize an author name for comparison."""
    import unicodedata
    # Normalize unicode (e.g., Brontë -> Bronte for comparison)
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    return name.lower().strip()


def _normalize_title(title):
    """Normalize a title for comparison."""
    import unicodedata
    title = unicodedata.normalize('NFKD', title)
    title = ''.join(c for c in title if not unicodedata.combining(c))
    return title.lower().strip()


def _title_match_score(book_data, query_title):
    """Score how well a book's title matches the query title. Higher is better."""
    if not query_title:
        return 0
    book_title = book_data.get('title', '')
    book_subtitle = book_data.get('subtitle', '')

    qt = _normalize_title(query_title)
    bt = _normalize_title(book_title)

    # Exact title match
    if bt == qt:
        return 20
    # Title starts with query or query starts with title
    if bt.startswith(qt) or qt.startswith(bt):
        return 15
    # Query title contained in book title
    if qt in bt:
        return 10
    # Book title contained in query
    if bt in qt:
        return 8
    # Check subtitle
    if book_subtitle:
        bs = _normalize_title(book_subtitle)
        if bs == qt or qt in bs:
            return 5
    return 0


def _author_match_score(book_data, query_authors):
    """Score how well a book's authors match the query authors. Higher is better."""
    book_authors = []
    for contrib in book_data.get('contributions', []):
        author = contrib.get('author', {})
        name = author.get('name')
        if name:
            book_authors.append(_normalize_author(name))

    if not book_authors or not query_authors:
        return 0

    score = 0
    for qa in query_authors:
        qa_norm = _normalize_author(qa)
        # Check for exact match
        if qa_norm in book_authors:
            score += 10
            continue
        # Check if query author's last name appears in any book author
        qa_parts = qa_norm.split()
        if qa_parts:
            last_name = qa_parts[-1]
            for ba in book_authors:
                if last_name in ba.split():
                    score += 5
                    break
    return score


def _rank_candidates(candidates, title, authors):
    """Rank candidates by combined author match, title match, and popularity."""
    scored = []
    for c in candidates:
        author_score = _author_match_score(c, authors) if authors else 0
        title_score = _title_match_score(c, title) if title else 0
        popularity = c.get('users_count', 0) or 0
        scored.append((c, author_score, title_score, popularity))
    # Sort by: author match, then title match, then popularity
    scored.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
    return [c for c, _, _, _ in scored]


def _parse_date(date_str):
    """Parse a date string into a datetime object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        try:
            return datetime.strptime(date_str, '%Y')
        except ValueError:
            return None


def _map_genres(cached_tags, genre_mappings, log, min_count=2):
    """Map Hardcover tags/genres to Calibre tags using the genre mapping.

    cached_tags is a dict like:
    {
        "Genre": [{"tag": "Classics", "count": 100, ...}, ...],
        "Mood": [{"tag": "dark", "count": 50, ...}, ...],
        "Tag": [...],
        "Content Warning": [...]
    }

    Genres in the mapping are always included (the mapping acts as a whitelist).
    Unmapped genres are only included if their count >= min_count.
    """
    tags = []
    if not cached_tags:
        return tags

    if isinstance(cached_tags, str):
        try:
            cached_tags = json.loads(cached_tags)
        except (json.JSONDecodeError, TypeError):
            return tags

    # Extract genre entries from the Genre category
    genre_entries = []
    if isinstance(cached_tags, dict):
        genres = cached_tags.get('Genre', [])
        for item in genres:
            if isinstance(item, dict):
                name = item.get('tag')
                count = item.get('count', 0)
                if name:
                    genre_entries.append((name, count))
            elif isinstance(item, str):
                genre_entries.append((item, 0))
    elif isinstance(cached_tags, list):
        for item in cached_tags:
            if isinstance(item, dict):
                name = item.get('tag') or item.get('name')
                count = item.get('count', 0)
                if name:
                    genre_entries.append((name, count))
            elif isinstance(item, str):
                genre_entries.append((item, 0))

    for name, count in genre_entries:
        if name in genre_mappings:
            # Mapped genres are always included (whitelist)
            mapped = genre_mappings[name]
            if mapped:  # Empty mapping means skip this genre
                tags.append(mapped)
        else:
            # Unmapped genres only included if they have enough votes
            if count >= min_count:
                tags.append(name)

    return tags


def _build_metadata(book_data, plugin, log):
    """Build a Calibre Metadata object from Hardcover book data."""
    title = book_data.get('title', '')

    # Authors — only include primary authors (contribution is null or "Author")
    authors = []
    contributions = book_data.get('contributions', [])
    for contrib in contributions:
        role = contrib.get('contribution')
        if role is None or role == 'Author':
            author = contrib.get('author', {})
            name = author.get('name')
            if name:
                authors.append(name)
    if not authors:
        authors = ['Unknown']

    mi = Metadata(title, authors)

    # Identifiers
    slug = book_data.get('slug', '')
    if slug:
        mi.set_identifier('hardcover', slug)

    # Rating (Hardcover uses 0-5, Calibre uses 0-10)
    rating = book_data.get('rating')
    if rating is not None:
        try:
            mi.rating = float(rating) * 2
        except (ValueError, TypeError):
            pass

    # Description (headline is a short tagline that precedes the description)
    headline = book_data.get('headline')
    description = book_data.get('description')
    if headline and description:
        mi.comments = '%s\n\n%s' % (headline, description)
    elif headline:
        mi.comments = headline
    elif description:
        mi.comments = description

    # Series
    book_series = book_data.get('book_series', [])
    if book_series:
        primary_series = book_series[0]
        series_info = primary_series.get('series', {})
        series_name = series_info.get('name')
        if series_name:
            mi.series = series_name
            pos = primary_series.get('position')
            if pos is not None:
                try:
                    mi.series_index = float(pos)
                except (ValueError, TypeError):
                    pass

    # Tags/Genres
    genre_mappings = plugin.prefs.get('genre_mappings', {})
    cached_tags = book_data.get('cached_tags')
    tags = _map_genres(cached_tags, genre_mappings, log)
    if tags:
        mi.tags = tags

    # Edition-specific data
    editions = book_data.get('editions', [])
    preferred_format = plugin.prefs.get('preferred_edition', 'ebook')
    edition = _select_preferred_edition(editions, preferred_format)

    if edition:
        # ISBN
        isbn_13 = edition.get('isbn_13')
        isbn_10 = edition.get('isbn_10')
        if isbn_13 and check_isbn(isbn_13):
            mi.set_identifier('isbn', isbn_13)
        elif isbn_10 and check_isbn(isbn_10):
            mi.set_identifier('isbn', isbn_10)

        # Publisher
        publisher = edition.get('publisher', {})
        if publisher:
            pub_name = publisher.get('name')
            if pub_name:
                mi.publisher = pub_name

        # Pages
        pages = edition.get('pages')
        if not pages:
            pages = book_data.get('pages')

        # Language
        language = edition.get('language', {})
        if language:
            lang_name = language.get('language')
            if lang_name:
                from calibre.utils.localization import canonicalize_lang
                canon = canonicalize_lang(lang_name)
                if canon:
                    mi.languages = [canon]

    # Publication date
    use_original = plugin.prefs.get('use_original_pub_date', True)
    if use_original:
        pub_date = _parse_date(book_data.get('release_date'))
    else:
        pub_date = None
        if edition:
            pub_date = _parse_date(edition.get('release_date'))
        if not pub_date:
            pub_date = _parse_date(book_data.get('release_date'))

    if pub_date:
        mi.pubdate = pub_date

    # Cover URL
    cover_url = None
    cached_image = book_data.get('cached_image')
    if cached_image:
        if isinstance(cached_image, str):
            try:
                cached_image = json.loads(cached_image)
            except (json.JSONDecodeError, TypeError):
                cached_image = None
        if isinstance(cached_image, dict):
            cover_url = cached_image.get('url')

    if cover_url:
        mi.has_cover = True
        # Cache the cover URL using Calibre's built-in mechanism
        slug = book_data.get('slug', '')
        if slug:
            plugin.cache_identifier_to_cover_url(slug, cover_url)

    # Source relevance
    mi.source_relevance = 0

    return mi


def identify(plugin, log, result_queue, abort, title=None, authors=None,
             identifiers=None, timeout=30):
    if not identifiers:
        identifiers = {}

    api_key = plugin.prefs.get('api_key', '')
    if not api_key:
        log.error('Hardcover API key not configured')
        return None

    book_ids = []

    # Try direct numeric Hardcover book ID first
    hardcover_book_id = identifiers.get('hardcover-id')
    if hardcover_book_id:
        try:
            book_ids.append(int(hardcover_book_id))
        except (ValueError, TypeError):
            pass

    # Try ISBN lookup
    if not book_ids:
        isbn = identifiers.get('isbn')
        if isbn and check_isbn(isbn):
            edition = _get_edition_by_isbn(api_key, isbn, log, timeout)
            if edition:
                book_id = edition.get('book_id') or edition.get('book', {}).get('id')
                if book_id:
                    book_ids.append(book_id)

    # Try Hardcover slug via search
    if not book_ids:
        hardcover_slug = identifiers.get('hardcover') or identifiers.get('hardcover-slug')
        if hardcover_slug:
            found_ids = _search_books(api_key, hardcover_slug.replace('-', ' '), log, timeout)
            for bid in found_ids:
                if bid not in book_ids:
                    book_ids.append(bid)

    # Search by title first
    if not book_ids and title:
        found_ids = _search_books(api_key, title, log, timeout)
        for bid in found_ids:
            if abort.is_set():
                return None
            if bid not in book_ids:
                book_ids.append(bid)

    # If title-only didn't work, try title+author combined
    if not book_ids and title and authors:
        query = '%s %s' % (title, ' '.join(authors))
        found_ids = _search_books(api_key, query, log, timeout)
        for bid in found_ids:
            if abort.is_set():
                return None
            if bid not in book_ids:
                book_ids.append(bid)

    # Fetch full details in a single batch request
    if abort.is_set():
        return None
    candidates = _get_books_by_ids(api_key, book_ids[:10], log, timeout)

    # Rank candidates by author match, title match, and popularity
    if candidates:
        candidates = _rank_candidates(candidates, title, authors)
        # Filter out candidates with low title relevance (Calibre would
        # discard them anyway during merge)
        if title:
            candidates = [c for c in candidates
                          if _title_match_score(c, title) >= 15]
        for c in candidates[:5]:
            a_score = _author_match_score(c, authors) if authors else 0
            t_score = _title_match_score(c, title) if title else 0
            pop = c.get('users_count', 0) or 0
            log('  Ranked: %s (author=%d, title=%d, users=%d)' %
                (c.get('slug', '?'), a_score, t_score, pop))

    for i, book_data in enumerate(candidates[:5]):
        mi = _build_metadata(book_data, plugin, log)
        mi.source_relevance = i
        result_queue.put(mi)

    return None


def download_cover(plugin, log, result_queue, abort, title=None, authors=None,
                   identifiers=None, timeout=30, get_best_cover=False):
    if not identifiers:
        identifiers = {}

    api_key = plugin.prefs.get('api_key', '')
    if not api_key:
        log.error('Hardcover API key not configured')
        return None

    # Try to find the book
    book_id = None

    # Try direct numeric ID
    hardcover_book_id = identifiers.get('hardcover-id')
    if hardcover_book_id:
        try:
            book_id = int(hardcover_book_id)
        except (ValueError, TypeError):
            pass

    # Try ISBN
    if not book_id:
        isbn = identifiers.get('isbn')
        if isbn:
            edition = _get_edition_by_isbn(api_key, isbn, log, timeout)
            if edition:
                book_id = edition.get('book_id') or edition.get('book', {}).get('id')

    # Try slug search
    if not book_id:
        hardcover_slug = identifiers.get('hardcover') or identifiers.get('hardcover-slug')
        if hardcover_slug:
            found_ids = _search_books(api_key, hardcover_slug.replace('-', ' '), log, timeout)
            if found_ids:
                book_id = found_ids[0]

    # Title search
    if not book_id and title:
        query = title
        if authors:
            query = '%s %s' % (title, ' '.join(authors))
        found_ids = _search_books(api_key, query, log, timeout)
        if found_ids:
            book_id = found_ids[0]

    if not book_id:
        return None

    book_data = _get_book_covers(api_key, book_id, log, timeout)
    if not book_data:
        return None

    def _extract_cover_url(cached_image):
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

    # Use the book-level cover — this is Hardcover's chosen display cover
    book_url = _extract_cover_url(book_data.get('cached_image'))
    if not book_url:
        log.error('No cover URL found for book')
        return None

    log('Downloading Hardcover book cover: %s' % book_url)

    from calibre import browser
    br = browser()

    try:
        response = br.open_novisit(book_url, timeout=timeout)
        cover_data = response.read()
        if cover_data:
            result_queue.put((plugin, cover_data))
    except Exception as e:
        log.error('Failed to download book cover: %s' % str(e))

    return None
