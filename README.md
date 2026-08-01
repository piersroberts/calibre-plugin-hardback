# Hardcover Metadata Plugin for Calibre

A Calibre metadata source plugin that fetches book metadata from [Hardcover](https://hardcover.app) using their GraphQL API.

## Features

- Search by title, author, or ISBN
- Downloads covers, descriptions, ratings, series info, publication dates
- **Preferred edition format**: defaults to ebook, configurable to physical or audiobook
- **Original publication date**: option to use the original book publication date rather than the edition's release date
- **Genre mapping**: fully configurable mapping from Hardcover genres/tags to Calibre tags

## Installation

1. Build the plugin zip:
   ```
   python build.py
   ```
2. In Calibre, go to **Preferences → Plugins → Load plugin from file** and select `hardcover-metadata.zip`

## Configuration

After installation, go to **Preferences → Plugins**, find "Hardcover Metadata" and click **Customize plugin**:

1. **API Key**: Get yours from https://hardcover.app/account/api
2. **Preferred Edition**: Choose ebook (default), physical, or audiobook — determines which edition's ISBN/publisher/language data to use
3. **Use Original Publication Date**: When checked (default), uses the book's original publication date rather than the specific edition's release date
4. **Genre Mappings**: Map Hardcover genres to your preferred Calibre tags. Format: `Hardcover Genre = Calibre Tag`. Set an empty mapping (`Genre =`) to exclude a genre entirely.

## API Notes

- The Hardcover API is in beta and may change
- Rate limited to 60 requests/minute
- Your API key expires after 1 year
- API docs: https://docs.hardcover.app/api/getting-started/
