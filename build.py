#!/usr/bin/env python
"""Package the plugin into a zip file for installation in Calibre."""
import os
import zipfile

PLUGIN_FILES = [
    '__init__.py',
    'config.py',
    'worker.py',
    'plugin-import-name-hardcover_metadata.txt',
]

OUTPUT = 'hardcover-metadata.zip'


def build():
    base = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base, OUTPUT)

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in PLUGIN_FILES:
            filepath = os.path.join(base, fname)
            zf.write(filepath, fname)

    print('Built plugin: %s' % output_path)


if __name__ == '__main__':
    build()
