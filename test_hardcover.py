"""Tests for Hardcover metadata plugin logic.

Run with: python test_hardcover.py
Requires the API key in .env file (KEY=Bearer ...).
"""
import json
import os
import sys
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

# Load API key from .env
env_path = Path(__file__).parent / '.env'
API_KEY = ''
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith('KEY='):
            API_KEY = line[4:].strip()

HARDCOVER_API_URL = 'https://api.hardcover.app/v1/graphql'


def graphql_request(query, variables=None):
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    data = json.dumps(payload).encode('utf-8')
    req = Request(HARDCOVER_API_URL, data=data)
    req.add_header('Content-Type', 'application/json')
    req.add_header('authorization', API_KEY)
    req.add_header('User-Agent', 'calibre-hardcover-test/1.0')
    response = urlopen(req, timeout=30)
    return json.loads(response.read().decode('utf-8'))


# === Ranking functions (copied for standalone testing) ===

def _normalize_title(title):
    title = unicodedata.normalize('NFKD', title)
    title = ''.join(c for c in title if not unicodedata.combining(c))
    return title.lower().strip()


def _normalize_author(name):
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    return name.lower().strip()


def _title_match_score(book_data, query_title):
    if not query_title:
        return 0
    book_title = book_data.get('title', '')
    qt = _normalize_title(query_title)
    bt = _normalize_title(book_title)
    if bt == qt:
        return 20
    if bt.startswith(qt) or qt.startswith(bt):
        return 15
    if qt in bt:
        return 10
    if bt in qt:
        return 8
    book_subtitle = book_data.get('subtitle', '')
    if book_subtitle:
        bs = _normalize_title(book_subtitle)
        if bs == qt or qt in bs:
            return 5
    return 0


def _author_match_score(book_data, query_authors):
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
        if qa_norm in book_authors:
            score += 10
            continue
        qa_parts = qa_norm.split()
        if qa_parts:
            last_name = qa_parts[-1]
            for ba in book_authors:
                if last_name in ba.split():
                    score += 5
                    break
    return score


def _rank_candidates(candidates, title, authors):
    scored = []
    for c in candidates:
        author_score = _author_match_score(c, authors) if authors else 0
        title_score = _title_match_score(c, title) if title else 0
        popularity = c.get('users_count', 0) or 0
        scored.append((c, author_score, title_score, popularity))
    scored.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
    return [c for c, _, _, _ in scored]


def _map_genres(cached_tags, genre_mappings, log, min_count=2):
    """Map Hardcover genres to Calibre tags with count filtering."""
    tags = []
    if not cached_tags:
        return tags
    if isinstance(cached_tags, str):
        cached_tags = json.loads(cached_tags)

    genre_entries = []
    if isinstance(cached_tags, dict):
        genres = cached_tags.get('Genre', [])
        for item in genres:
            if isinstance(item, dict):
                name = item.get('tag')
                count = item.get('count', 0)
                if name:
                    genre_entries.append((name, count))

    for name, count in genre_entries:
        if name in genre_mappings:
            mapped = genre_mappings[name]
            if mapped:
                tags.append(mapped)
        else:
            if count >= min_count:
                tags.append(name)
    return tags


EDITION_FORMAT_MAP = {'ebook': 4, 'physical': 1, 'audiobook': 2}


def _select_preferred_edition(editions, preferred_format):
    """Select the best edition based on user preference."""
    format_id = EDITION_FORMAT_MAP.get(preferred_format, 4)

    for ed in editions:
        if ed.get('reading_format_id') == format_id:
            if ed.get('isbn_13') or ed.get('isbn_10'):
                return ed
    for ed in editions:
        if ed.get('reading_format_id') == format_id:
            return ed
    for ed in editions:
        if ed.get('isbn_13') or ed.get('isbn_10'):
            return ed
    return editions[0] if editions else None


# === Tests ===

def test_search_returns_ids():
    """Search API returns a list of integer book IDs."""
    gql = '''
    query {
        search(query: "Wuthering Heights", query_type: "Book", per_page: 5, page: 1) {
            ids
        }
    }
    '''
    result = graphql_request(gql)
    assert 'errors' not in result, f"GraphQL errors: {result['errors']}"
    ids = result['data']['search']['ids']
    assert isinstance(ids, list)
    assert len(ids) > 0
    assert all(isinstance(i, int) for i in ids)
    # The canonical Wuthering Heights (386401) should be in results
    assert 386401 in ids, f"Expected 386401 in {ids}"
    print("PASS: test_search_returns_ids")


def test_book_detail_query():
    """Book detail query returns expected fields without errors."""
    gql = '''
    query {
        books(where: {id: {_eq: 386401}}) {
            id
            title
            subtitle
            slug
            description
            rating
            ratings_count
            users_count
            release_date
            cached_image
            cached_tags
            contributions {
                author { name }
            }
            book_series {
                series { name }
                position
            }
            editions {
                id
                isbn_13
                reading_format_id
                publisher { name }
            }
        }
    }
    '''
    result = graphql_request(gql)
    assert 'errors' not in result, f"GraphQL errors: {result['errors']}"
    books = result['data']['books']
    assert len(books) == 1
    book = books[0]
    assert book['title'] == 'Wuthering Heights'
    assert book['slug'] == 'wuthering-heights'
    assert book['users_count'] > 1000
    assert any(c['author']['name'] == 'Emily Brontë' for c in book['contributions'])
    assert len(book['editions']) > 0
    print("PASS: test_book_detail_query")


def test_isbn_lookup():
    """Edition lookup by ISBN returns the correct book."""
    gql = '''
    query {
        editions(where: {isbn_13: {_eq: "9781435171503"}}) {
            id
            book_id
            book { id title slug }
        }
    }
    '''
    result = graphql_request(gql)
    assert 'errors' not in result, f"GraphQL errors: {result['errors']}"
    editions = result['data']['editions']
    assert len(editions) >= 1
    assert editions[0]['book']['slug'] == 'wuthering-heights'
    assert editions[0]['book_id'] == 386401
    print("PASS: test_isbn_lookup")


def test_edition_format_selection():
    """Ebook editions are available and have reading_format_id=4."""
    gql = '''
    query {
        editions(where: {book_id: {_eq: 386401}, reading_format_id: {_eq: 4}}, limit: 5) {
            id
            isbn_13
            reading_format_id
            edition_format
            publisher { name }
        }
    }
    '''
    result = graphql_request(gql)
    assert 'errors' not in result, f"GraphQL errors: {result['errors']}"
    editions = result['data']['editions']
    assert len(editions) > 0, "No ebook editions found for Wuthering Heights"
    for ed in editions:
        assert ed['reading_format_id'] == 4
    print("PASS: test_edition_format_selection")


def test_ranking_wuthering_heights():
    """The canonical Wuthering Heights ranks first for the query."""
    # Fetch all search results
    gql = '''
    query {
        search(query: "Wuthering Heights", query_type: "Book", per_page: 10, page: 1) {
            ids
        }
    }
    '''
    result = graphql_request(gql)
    ids = result['data']['search']['ids']

    # Fetch book details for all
    gql2 = '''
    query GetBooks($ids: [Int!]!) {
        books(where: {id: {_in: $ids}}) {
            id
            title
            subtitle
            slug
            users_count
            contributions {
                author { name }
            }
        }
    }
    '''
    result2 = graphql_request(gql2, {'ids': ids})
    books = result2['data']['books']

    # Rank them
    ranked = _rank_candidates(books, 'Wuthering Heights', ['Emily Brontë'])

    # The canonical version should be first
    assert ranked[0]['id'] == 386401, (
        f"Expected 386401 first, got {ranked[0]['id']} ({ranked[0]['slug']})"
    )
    assert ranked[0]['slug'] == 'wuthering-heights'
    print("PASS: test_ranking_wuthering_heights")


def test_ranking_multiauthor():
    """Multi-author book search ranks correctly."""
    books = [
        {'id': 1, 'title': 'Good Omens', 'users_count': 5000,
         'contributions': [{'author': {'name': 'Terry Pratchett'}}, {'author': {'name': 'Neil Gaiman'}}]},
        {'id': 2, 'title': 'Good Omens: The Script Book', 'users_count': 200,
         'contributions': [{'author': {'name': 'Neil Gaiman'}}]},
        {'id': 3, 'title': 'Good Omens', 'users_count': 10,
         'contributions': [{'author': {'name': 'Someone Else'}}]},
    ]
    ranked = _rank_candidates(books, 'Good Omens', ['Terry Pratchett', 'Neil Gaiman'])
    assert ranked[0]['id'] == 1, f"Expected id=1 first, got {ranked[0]['id']}"
    print("PASS: test_ranking_multiauthor")


def test_ranking_alchemist():
    """The Alchemist by Paulo Coelho ranks first when author is in query."""
    books = [
        {'id': 1, 'title': 'The Alchemist', 'users_count': 55,
         'contributions': [{'author': {'name': 'Paolo Bacigalupi'}}]},
        {'id': 2, 'title': 'The Alchemist', 'users_count': 57,
         'contributions': [{'author': {'name': 'H. P. Lovecraft'}}]},
        {'id': 3, 'title': 'The Alchemist', 'users_count': 6778,
         'contributions': [{'author': {'name': 'Paulo Coelho'}}]},
        {'id': 4, 'title': 'The Alchemist', 'users_count': 4,
         'contributions': [{'author': {'name': 'Megan Derr'}}]},
    ]
    ranked = _rank_candidates(books, 'The Alchemist',
                              ['Alan R. Clarke', 'James Noel Smith', 'Paulo Coelho'])
    assert ranked[0]['id'] == 3, f"Expected id=3 (Coelho) first, got {ranked[0]['id']}"
    print("PASS: test_ranking_alchemist")


def test_ranking_title_exact_beats_partial():
    """Exact title match ranks higher than partial."""
    books = [
        {'id': 1, 'title': 'The Lord of the Rings: The Fellowship of the Ring',
         'users_count': 3000, 'contributions': [{'author': {'name': 'J.R.R. Tolkien'}}]},
        {'id': 2, 'title': 'The Fellowship of the Ring',
         'users_count': 8000, 'contributions': [{'author': {'name': 'J.R.R. Tolkien'}}]},
    ]
    ranked = _rank_candidates(books, 'The Fellowship of the Ring', ['J.R.R. Tolkien'])
    assert ranked[0]['id'] == 2, f"Expected id=2 first, got {ranked[0]['id']}"
    print("PASS: test_ranking_title_exact_beats_partial")


def test_normalize_unicode():
    """Unicode normalization handles accented characters."""
    assert _normalize_author('Emily Brontë') == 'emily bronte'
    assert _normalize_author('García Márquez') == 'garcia marquez'
    assert _normalize_title('Wuthering Heights') == 'wuthering heights'
    print("PASS: test_normalize_unicode")


def test_genre_filtering():
    """Genre mapping filters low-count junk tags and maps known genres."""
    genre_mappings = {
        'Classics': 'Classics',
        'Fiction': 'Fiction',
        'Historical Fiction': 'Historical Fiction',
        'Fantasy': 'Fantasy',
    }

    cached_tags = {
        'Genre': [
            {'tag': 'Classics', 'count': 50},
            {'tag': 'Fiction', 'count': 30},
            {'tag': 'Foreign Language Study', 'count': 1},
            {'tag': 'Comics & Graphic Novels', 'count': 1},
            {'tag': 'Detective and mystery stories', 'count': 1},
            {'tag': 'Historical Fiction', 'count': 5},
            {'tag': 'Rare Unmapped Genre', 'count': 10},
        ]
    }

    tags = _map_genres(cached_tags, genre_mappings, print, min_count=2)

    # Mapped genres always included regardless of count
    assert 'Classics' in tags
    assert 'Historical Fiction' in tags

    # Unmapped genres with count >= 2 are included
    assert 'Rare Unmapped Genre' in tags

    # Junk tags with count=1 that aren't in mapping are excluded
    assert 'Foreign Language Study' not in tags
    assert 'Comics & Graphic Novels' not in tags
    assert 'Detective and mystery stories' not in tags

    print("PASS: test_genre_filtering")


def test_genre_empty_mapping_excludes():
    """Empty mapping value excludes a genre entirely."""
    mappings = {'Classics': 'Classics', 'Fiction': ''}  # Fiction mapped to empty = skip

    cached_tags = {
        'Genre': [
            {'tag': 'Classics', 'count': 50},
            {'tag': 'Fiction', 'count': 30},
        ]
    }

    tags = _map_genres(cached_tags, mappings, print, min_count=2)
    assert 'Classics' in tags
    assert 'Fiction' not in tags
    assert '' not in tags
    print("PASS: test_genre_empty_mapping_excludes")


def test_author_role_filtering():
    """Only primary authors are included, not editors/translators."""
    gql = '''
    query {
        books(where: {id: {_eq: 386401}}) {
            contributions {
                author { name }
                contribution
            }
        }
    }
    '''
    result = graphql_request(gql)
    contributions = result['data']['books'][0]['contributions']

    # Filter like our plugin does
    authors = []
    for contrib in contributions:
        role = contrib.get('contribution')
        if role is None or role == 'Author':
            name = contrib['author']['name']
            authors.append(name)

    assert 'Emily Brontë' in authors
    assert 'Richard J. Dunn' not in authors  # He's an Editor
    print("PASS: test_author_role_filtering")


def test_edition_prefers_isbn():
    """Edition selector prefers editions with ISBN over those without."""
    editions = [
        {'id': 1, 'reading_format_id': 4, 'isbn_13': None, 'isbn_10': None},
        {'id': 2, 'reading_format_id': 4, 'isbn_13': '9781444737226', 'isbn_10': '1444737228'},
        {'id': 3, 'reading_format_id': 1, 'isbn_13': '9780123456789', 'isbn_10': None},
    ]

    selected = _select_preferred_edition(editions, 'ebook')
    assert selected['id'] == 2, f"Expected edition 2 (ebook with ISBN), got {selected['id']}"

    # If no ebook has ISBN, still picks an ebook
    editions_no_isbn = [
        {'id': 1, 'reading_format_id': 4, 'isbn_13': None, 'isbn_10': None},
        {'id': 3, 'reading_format_id': 1, 'isbn_13': '9780123456789', 'isbn_10': None},
    ]
    selected2 = _select_preferred_edition(editions_no_isbn, 'ebook')
    assert selected2['id'] == 1, f"Expected edition 1 (ebook without ISBN), got {selected2['id']}"

    print("PASS: test_edition_prefers_isbn")


def test_cover_query_lightweight():
    """Cover query returns edition images without heavy nested data."""
    gql = '''
    query {
        books(where: {id: {_eq: 427513}}) {
            id
            cached_image
            editions(order_by: {users_count: desc}, limit: 5) {
                id
                cached_image
            }
        }
    }
    '''
    result = graphql_request(gql)
    assert 'errors' not in result, f"GraphQL errors: {result['errors']}"
    book = result['data']['books'][0]
    assert book['cached_image'] is not None
    assert 'url' in book['cached_image']
    assert len(book['editions']) > 0
    # At least some editions should have covers
    covers = [e for e in book['editions'] if e.get('cached_image') and e['cached_image'].get('url')]
    assert len(covers) > 0, "No edition covers found"
    print("PASS: test_cover_query_lightweight")


if __name__ == '__main__':
    if not API_KEY:
        print("ERROR: No API key found in .env file")
        sys.exit(1)

    # Offline tests (no API needed)
    test_normalize_unicode()
    test_ranking_multiauthor()
    test_ranking_alchemist()
    test_ranking_title_exact_beats_partial()
    test_genre_filtering()
    test_genre_empty_mapping_excludes()
    test_edition_prefers_isbn()

    # Online tests (need API key)
    test_search_returns_ids()
    test_book_detail_query()
    test_isbn_lookup()
    test_edition_format_selection()
    test_ranking_wuthering_heights()
    test_author_role_filtering()
    test_cover_query_lightweight()

    print("\nAll tests passed!")
