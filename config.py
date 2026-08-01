from qt.core import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                      QCheckBox, QGroupBox, QPlainTextEdit, QComboBox)

DEFAULT_GENRE_MAPPINGS = {
    # Hardcover genre -> Calibre tag
    'Science Fiction': 'Science Fiction',
    'Fantasy': 'Fantasy',
    'Mystery': 'Mystery',
    'Thriller': 'Thriller',
    'Romance': 'Romance',
    'Horror': 'Horror',
    'Historical Fiction': 'Historical Fiction',
    'Literary Fiction': 'Literary Fiction',
    'Nonfiction': 'Nonfiction',
    'Biography': 'Biography',
    'Memoir': 'Memoir',
    'Self-Help': 'Self-Help',
    'Science': 'Science',
    'History': 'History',
    'Philosophy': 'Philosophy',
    'Poetry': 'Poetry',
    'Humor': 'Humor',
    'Young Adult': 'Young Adult',
    'Children': 'Children',
    'Graphic Novel': 'Graphic Novel',
    'Crime': 'Crime',
    'Adventure': 'Adventure',
    'Dystopian': 'Dystopian',
    'Contemporary': 'Contemporary',
    'Classics': 'Classics',
    'Urban Fantasy': 'Urban Fantasy',
    'Epic Fantasy': 'Epic Fantasy',
    'Space Opera': 'Space Opera',
    'Cyberpunk': 'Cyberpunk',
    'Steampunk': 'Steampunk',
    'Dark Fantasy': 'Dark Fantasy',
    'Paranormal': 'Paranormal',
    'Cozy Mystery': 'Cozy Mystery',
    'Historical Romance': 'Historical Romance',
    'Contemporary Romance': 'Contemporary Romance',
    'True Crime': 'True Crime',
    'Psychology': 'Psychology',
    'Business': 'Business',
    'Economics': 'Economics',
    'Politics': 'Politics',
    'Travel': 'Travel',
    'Cooking': 'Cooking',
    'Art': 'Art',
    'Music': 'Music',
    'Sports': 'Sports',
    'Religion': 'Religion',
    'Spirituality': 'Spirituality',
    'Technology': 'Technology',
    'Programming': 'Programming',
}

PREFS_DEFAULTS = {
    'api_key': '',
    'preferred_edition': 'ebook',  # ebook, physical, audiobook
    'preferred_language': 'English',
    'use_original_pub_date': True,
    'genre_mappings': DEFAULT_GENRE_MAPPINGS,
}


class ConfigWidget(QWidget):

    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.prefs = plugin.prefs
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # API Key
        api_group = QGroupBox('API Settings')
        api_layout = QVBoxLayout()
        api_group.setLayout(api_layout)

        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel('API Key:'))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setText(self.prefs['api_key'])
        self.api_key_edit.setPlaceholderText('Enter your Hardcover API key')
        key_layout.addWidget(self.api_key_edit)
        api_layout.addLayout(key_layout)

        api_layout.addWidget(QLabel(
            '<a href="https://hardcover.app/account/api">Get your API key from Hardcover</a>'
        ))

        layout.addWidget(api_group)

        # Edition Preferences
        edition_group = QGroupBox('Edition Preferences')
        edition_layout = QVBoxLayout()
        edition_group.setLayout(edition_layout)

        pref_layout = QHBoxLayout()
        pref_layout.addWidget(QLabel('Preferred edition format:'))
        self.edition_combo = QComboBox()
        self.edition_combo.addItems(['ebook', 'physical', 'audiobook'])
        current = self.prefs['preferred_edition']
        idx = self.edition_combo.findText(current)
        if idx >= 0:
            self.edition_combo.setCurrentIndex(idx)
        pref_layout.addWidget(self.edition_combo)
        edition_layout.addLayout(pref_layout)

        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel('Preferred cover language:'))
        self.language_edit = QLineEdit()
        self.language_edit.setText(self.prefs['preferred_language'])
        self.language_edit.setPlaceholderText('English')
        lang_layout.addWidget(self.language_edit)
        edition_layout.addLayout(lang_layout)

        layout.addWidget(edition_group)

        # Publication Date
        date_group = QGroupBox('Publication Date')
        date_layout = QVBoxLayout()
        date_group.setLayout(date_layout)

        self.use_original_date_cb = QCheckBox(
            'Use original publication date (instead of edition date)')
        self.use_original_date_cb.setChecked(self.prefs['use_original_pub_date'])
        date_layout.addWidget(self.use_original_date_cb)

        layout.addWidget(date_group)

        # Genre Mappings
        genre_group = QGroupBox('Genre Mappings')
        genre_layout = QVBoxLayout()
        genre_group.setLayout(genre_layout)

        genre_layout.addWidget(QLabel(
            'Map Hardcover genres to Calibre tags (one per line, format: '
            'Hardcover Genre = Calibre Tag).\n'
            'Lines starting with # are ignored. '
            'To exclude a genre, map it to nothing: Genre ='
        ))

        self.genre_edit = QPlainTextEdit()
        mappings = self.prefs['genre_mappings']
        lines = []
        for hc_genre, calibre_tag in sorted(mappings.items()):
            lines.append('%s = %s' % (hc_genre, calibre_tag))
        self.genre_edit.setPlainText('\n'.join(lines))
        self.genre_edit.setMinimumHeight(200)
        genre_layout.addWidget(self.genre_edit)

        layout.addWidget(genre_group)

    def save_settings(self):
        self.prefs['api_key'] = self.api_key_edit.text().strip()
        self.prefs['preferred_edition'] = self.edition_combo.currentText()
        self.prefs['preferred_language'] = self.language_edit.text().strip() or 'English'
        self.prefs['use_original_pub_date'] = self.use_original_date_cb.isChecked()

        # Parse genre mappings
        mappings = {}
        for line in self.genre_edit.toPlainText().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                parts = line.split('=', 1)
                hc_genre = parts[0].strip()
                calibre_tag = parts[1].strip()
                if hc_genre:
                    mappings[hc_genre] = calibre_tag
        self.prefs['genre_mappings'] = mappings
