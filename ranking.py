"""Book candidate ranking by title, author, and popularity."""
import unicodedata


def normalize_text(text):
    """Normalize text for comparison (strip accents, lowercase)."""
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def title_match_score(book_data, query_title):
    """Score how well a book's title matches the query. Higher is better.

    20 = exact match
    15 = starts-with match
    10 = query contained in title
    8  = title contained in query
    5  = matches subtitle
    0  = no match
    """
    if not query_title:
        return 0

    qt = normalize_text(query_title)
    bt = normalize_text(book_data.get('title', ''))

    if bt == qt:
        return 20
    if bt.startswith(qt) or qt.startswith(bt):
        return 15
    if qt in bt:
        return 10
    if bt in qt:
        return 8

    subtitle = book_data.get('subtitle', '')
    if subtitle:
        bs = normalize_text(subtitle)
        if bs == qt or qt in bs:
            return 5

    return 0


def author_match_score(book_data, query_authors):
    """Score how well a book's authors match the query authors.

    10 points per exact author match, 5 per last-name match.
    """
    if not query_authors:
        return 0

    book_authors = []
    for contrib in book_data.get('contributions', []):
        name = contrib.get('author', {}).get('name')
        if name:
            book_authors.append(normalize_text(name))

    if not book_authors:
        return 0

    score = 0
    for qa in query_authors:
        qa_norm = normalize_text(qa)
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


def rank_candidates(candidates, title, authors):
    """Sort candidates by (author_score, title_score, popularity) descending."""
    def sort_key(book):
        return (
            author_match_score(book, authors) if authors else 0,
            title_match_score(book, title) if title else 0,
            book.get('users_count', 0) or 0,
        )
    return sorted(candidates, key=sort_key, reverse=True)
