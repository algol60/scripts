#

# A script that modifies folium to work offline.
# Folium requires files that are typically downloaded from CDNs.
# This doesn't work if there is no Internet.
# Therefore, we look through the folium .py files for https URLs,
# update the .py files with a local URL, and overwrite the .py files.
#
# TODO downloaded .css files contain url() links; fix these as well.

import argparse
from pathlib import Path
import re
import requests
import sys

# For our purposes, a URL is a quoted string containing https://...
# where ... are any non-quote characters.
#
URL_RE = URL_RE = re.compile('''['"](https://[^'"]+)['"]''', re.IGNORECASE)
URL_CSS_RE = re.compile()

def url_to_name(u):
    """Convert a URL to a plain filename.

    Remove the leading 'https://'; change all '/' to '_'.
    """

    if not u.startswith('https://'):
        raise ValueError('Convert a URL, not "{u}"')

    u = u[8:].replace('/', '_')

    return u

class UrlModifier:
    def __init__(self, local_url):
        while local_url.endswith('/'):
            local_url = local_url[:-1]

        self.local_url = local_url
        self.downloads = []

    def local_https(self, line):
        """If this line contains a URL, modify it to contain a local URL.

        The old URL and new name are recorded in self.downloads.
        """

        m = URL_RE.search(line)
        if not m:
            return line

        sline = line.strip()
        if sline.startswith(('>>>', '...')):
            # This looks like a docstring, so leave it alone.
            #
            return line

        print(line, end='')
        b, e = m.span()
        old_u = line[b+1:e-1]
        name = url_to_name(old_u)

        line = f'{line[:b+1]}{self.local_url}/{name}{line[e-1:]}'
        print(line)

        self.downloads.append((old_u, name))

        return line

    def process(self, folium_dir):
        for p in folium_dir.glob('**/*.py'):
            print('--', p)
            with p.open(encoding='UTF-8') as f:
                old_lines = f.readlines()
                upd_lines = [self.local_https(line) for line in old_lines]
                if upd_lines!=old_lines:
                    with p.open('w', newline='', encoding='UTF_8') as f:
                        f.writelines(upd_lines)

    def download_to(self, local_dir):
        for old_u, name in um.downloads:
            print(f'{old_u}\n{name}\n')

            r = requests.get(old_u)
            local_file = local_dir / name
            with local_file.open('wb') as f:
                f.write(r.content)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='local_folium',
        description='Update folium .py files to use local versions of CDN files'
    )

    parser.add_argument('--dir', help='Root directory of folium files')
    parser.add_argument('--url', help='The base of the local URL')
    parser.add_argument('--download', help='Download the files to the specified directory')

    args = parser.parse_args()

    if not args.dir:
        print('Must specify the folium root directory.')
        sys.exit(1)

    if not args.url:
        print('Must specify the replacement base URL')
        sys.exit(2)

    if args.download:
        local_dir = Path(args.download)
        if not local_dir.is_dir():
            print('Download directory {d} doe snot exist')
            sys.exit(3)

    repl_url = args.url

    um = UrlModifier(args.url)
    um.process(Path(args.dir))

    if args.download:
        local_dir = Path(args.download)
        um.download_to(local_dir)
