from distutils.core import setup
setup(
    name = 'metafix',
    packages = ['metafix'],
    version = '1.2.1',
    description = 'Provides validation and safe, automated repair of audio metadata. Supports MP3, FLAC, and other popular formats.',
    url = 'https://github.com/spiritualized/metafix',
    download_url = 'https://github.com/spiritualized/metafix/archive/v1.2.1.tar.gz',
    keywords = ['metadata', 'validation', 'mp3', 'flac', 'python', 'library'],
    install_requires = [
                    'cleartag>=1.2.1',
                    'lastfmcache>=1.2.4',
                    'ordered-set>=3.1.1',
                ],

    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3.6',
    ],
)
