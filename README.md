# Hardcover Metadata Plugin for Calibre

A Calibre metadata source plugin that fetches book metadata and covers from [Hardcover](https://hardcover.app) using their GraphQL API.

## Features

- Search by title, author, or ISBN
- Downloads covers, descriptions, ratings, series info, publication dates, and languages
- Smart result ranking by author match, title match, and popularity
- Only includes primary authors (filters out editors, translators, etc.)
- **Preferred edition format**: defaults to ebook, configurable to physical or audiobook — determines which edition's ISBN/publisher/language data to use
- **Preferred cover language**: cover art is selected from the most popular non-audiobook edition in your preferred language (defaults to English)
- **Original publication date**: option to use the original book publication date rather than the edition's release date
- **Genre mapping**: configurable mapping from Hardcover genres to Calibre tags, with automatic filtering of low-confidence tags

## Installation

1. Build the plugin zip:
   ```
   python build.py
   ```
2. In Calibre, go to **Preferences → Plugins → Load plugin from file** and select `hardcover-metadata.zip`

## Configuration

After installation, go to **Preferences → Plugins**, find "Hardcover Metadata" and click **Customize plugin**:

1. **API Key**: Get yours from https://hardcover.app/account/api
2. **Preferred Edition Format**: Choose ebook (default), physical, or audiobook — controls which edition's ISBN, publisher, and language data is used for metadata
3. **Preferred Cover Language**: The language of the edition to use for cover art (default: English) — picks the most popular non-audiobook edition in that language
4. **Use Original Publication Date**: When checked (default), uses the book's original publication date rather than the specific edition's release date
5. **Genre Mappings**: Map Hardcover genres to your preferred Calibre tags. Format: `Hardcover Genre = Calibre Tag`. Set an empty mapping (`Genre =`) to exclude a genre. Unmapped genres are included only if they have significant community agreement (2+ votes)

## Running Tests

```
python test_hardcover.py
```

Requires an API key in a `.env` file (`KEY=Bearer ...`). Tests cover search, ranking, genre filtering, author role filtering, edition selection, and cover queries.

## API Notes

- The Hardcover API is in beta and may change
- Rate limited to 60 requests/minute
- Queries have a max timeout of 30 seconds
- Your API key expires after 1 year
- API docs: https://docs.hardcover.app/api/getting-started/
