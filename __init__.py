from calibre.ebooks.metadata.sources.base import Source


class HardcoverMetadata(Source):
    name = 'Hardcover Metadata'
    description = 'Downloads metadata and covers from Hardcover (hardcover.app)'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Piers'
    version = (1, 1, 0)
    minimum_calibre_version = (5, 0, 0)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset([
        'title', 'authors', 'identifier:hardcover', 'identifier:isbn',
        'rating', 'comments', 'publisher', 'pubdate', 'tags', 'series',
        'series_index', 'languages'
    ])

    cached_cover_url_is_reliable = True

    def is_configured(self):
        return bool(self.prefs.get('api_key'))

    @property
    def prefs(self):
        if not hasattr(self, '_prefs') or self._prefs is None:
            from calibre.utils.config import JSONConfig
            from calibre_plugins.hardcover_metadata.config import PREFS_DEFAULTS
            self._prefs = JSONConfig('plugins/hardcover_metadata')
            self._prefs.defaults = PREFS_DEFAULTS
        return self._prefs

    def get_cached_cover_url(self, identifiers):
        return self.cached_identifier_to_cover_url(
            identifiers.get('hardcover', ''))

    def config_widget(self):
        from calibre_plugins.hardcover_metadata.config import ConfigWidget
        return ConfigWidget(self)

    def save_settings(self, config_widget):
        config_widget.save_settings()

    def identify(self, log, result_queue, abort, title=None, authors=None,
                 identifiers=None, timeout=30):
        from calibre_plugins.hardcover_metadata.identify import identify
        return identify(self, log, result_queue, abort, title, authors,
                        identifiers, timeout)

    def download_cover(self, log, result_queue, abort, title=None, authors=None,
                       identifiers=None, timeout=30, get_best_cover=False):
        from calibre_plugins.hardcover_metadata.covers import download_cover
        return download_cover(self, log, result_queue, abort, title, authors,
                              identifiers, timeout, get_best_cover)

    def identify_results_keygen(self, title=None, authors=None, identifiers=None):
        def keygen(mi):
            return mi.source_relevance
        return keygen

    def get_book_url(self, identifiers):
        hardcover_id = identifiers.get('hardcover')
        if hardcover_id:
            return ('hardcover', hardcover_id,
                    'https://hardcover.app/books/%s' % hardcover_id)
        return None

    def id_from_url(self, url):
        import re
        match = re.match(r'https?://hardcover\.app/books/([^/?#]+)', url)
        if match:
            return ('hardcover', match.group(1))
        return None
