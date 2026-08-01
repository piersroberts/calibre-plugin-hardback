"""Hardcover GraphQL API client."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


API_URL = 'https://api.hardcover.app/v1/graphql'
USER_AGENT = 'calibre-hardcover-metadata-plugin/1.0'


def graphql_request(api_key, query, variables=None, timeout=30):
    """Execute a GraphQL request against the Hardcover API."""
    payload = {'query': query}
    if variables:
        payload['variables'] = variables

    data = json.dumps(payload).encode('utf-8')
    req = Request(API_URL, data=data)
    req.add_header('Content-Type', 'application/json')
    req.add_header('authorization', api_key)
    req.add_header('User-Agent', USER_AGENT)

    response = urlopen(req, timeout=timeout)
    return json.loads(response.read().decode('utf-8'))


def search_books(api_key, query, log, timeout=30):
    """Search for books by query string. Returns a list of book IDs."""
    gql = '''
    query SearchBooks($query: String!) {
        search(query: $query, query_type: "Book", per_page: 10, page: 1) {
            ids
        }
    }
    '''
    try:
        result = graphql_request(api_key, gql, {'query': query}, timeout)
        if 'errors' in result:
            log.error('Hardcover search error:', result['errors'])
            return []
        ids = result.get('data', {}).get('search', {}).get('ids', [])
        if isinstance(ids, str):
            ids = json.loads(ids)
        return [int(i) for i in ids if i]
    except (HTTPError, URLError) as e:
        log.error('Hardcover API request failed:', str(e))
        return []
    except (ValueError, TypeError) as e:
        log.error('Hardcover search parse error:', str(e))
        return []


def get_books(api_key, book_ids, log, timeout=30):
    """Fetch full details for multiple books in a single batch request."""
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
                author { name }
                contribution
            }
            book_series {
                series { name }
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
                language { language }
                publisher { name }
            }
        }
    }
    '''
    try:
        result = graphql_request(api_key, gql, {'ids': book_ids}, timeout)
        if 'errors' in result:
            log.error('Hardcover book detail error:', result['errors'])
            return []
        return result.get('data', {}).get('books', [])
    except (HTTPError, URLError) as e:
        log.error('Hardcover API request failed:', str(e))
        return []


def get_book_cover(api_key, book_id, language, log, timeout=30):
    """Fetch the most popular non-audiobook edition cover for a book
    in the given language. Returns book data with filtered editions."""
    gql = '''
    query GetBookCover($id: Int!, $language: String!) {
        books(where: {id: {_eq: $id}}) {
            id
            cached_image
            editions(
                where: {
                    reading_format_id: {_nin: [2]}
                    language: {language: {_eq: $language}}
                }
                order_by: {users_count: desc}
                limit: 1
            ) {
                id
                cached_image
                users_count
            }
        }
    }
    '''
    try:
        result = graphql_request(api_key, gql,
                                 {'id': book_id, 'language': language}, timeout)
        if 'errors' in result:
            log.error('Hardcover cover query error:', result['errors'])
            return None
        books = result.get('data', {}).get('books', [])
        return books[0] if books else None
    except (HTTPError, URLError) as e:
        log.error('Hardcover API request failed:', str(e))
        return None


def get_edition_by_isbn(api_key, isbn, log, timeout=30):
    """Look up an edition by ISBN. Returns edition dict or None."""
    field = 'isbn_13' if len(isbn) == 13 else 'isbn_10'
    gql = '''
    query GetEdition($isbn: String!) {
        editions(where: {%s: {_eq: $isbn}}) {
            id
            book_id
            book { id title slug }
        }
    }
    ''' % field
    try:
        result = graphql_request(api_key, gql, {'isbn': isbn}, timeout)
        if 'errors' in result:
            return None
        editions = result.get('data', {}).get('editions', [])
        return editions[0] if editions else None
    except (HTTPError, URLError):
        return None
