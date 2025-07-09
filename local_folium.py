#

# A script that modifies folium to work offline.
# Folium requires files that are typically downloaded from CDNs.
# This doesn't work if there is no Internet.
# Therefore, we look through the folium .py files for https URLs,
# update the .py files with a local URL, and overwrite the .py files.
#
# Extra step: downloaded CSS files themselves contain references to
# Internet files using url(). Thes also have to be processed.
# For each .css file, look for url(), determine the right thing to download
# (taking relative URLs into account), and update the .css file.
#
# Note that all downloaded files are written to files called (sha1 of URL).ext.
# This ensures that unique URLs produce unique filenames, and avoids mucking
# about with directory trees. The mapping from original URL to downloaded
# file is stored in zzdownloaded.json.
#
# To modify the folium source code at D:\tmp\git\folium\folium to use http://localhost:8000 and download the files to D:\tmp\cdn
# python .\local_folium.py --dir D:\tmp\git\folium\folium --url http://localhost:8000 --download D:\tmp\cdn
#

import argparse
from hashlib import sha1
import json
from pathlib import Path
import re
import requests
import sys

# For our purposes, a URL is a quoted string containing https://...
# where ... are any non-quote characters.
#
URL_RE = URL_RE = re.compile(r'''['"](https://[^'"]+)['"]''', re.IGNORECASE)

# CSS file scontain references in url() function calls.
#
CSS_RE = re.compile(r'''url\(([^)]+)\)''')

def url_relative(u, r):
    """Given a URL u, produce a modified URL using relative path r."""

    s = u.rfind('/')
    u = u[:s]

    while r.startswith('../'):
        s = u.rfind('/')
        u = u[:s]
        r = r[3:]

    return f'{u}/{r}'

def url_to_name(u):
    """Convert a URL to a plain filename.

    Hash the URL and maintain the suffix.
    """

    if u.startswith('//'):
        # Relative protocol in CSS files.
        #
        u = f'https:{u}'

    if not u.startswith('https://'):
        raise ValueError('Convert a URL, not "{u}"')

    name = sha1(u.encode('UTF-8')).hexdigest()

    return f'{name}{Path(u).suffix}'

class UrlModifier:
    def __init__(self, local_url):
        while local_url.endswith('/'):
            local_url = local_url[:-1]

        self.local_url = local_url

        # Map original URLS to local URLs.
        #
        self.url_map = {}

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
        if old_u not in self.url_map:
            name = url_to_name(old_u)

            line = f'{line[:b+1]}{self.local_url}/{name}{line[e-1:]}'
            print(line)

            self.url_map[old_u] = name

        return line

    def process_py(self, folium_dir):
        """Look for https URLs in strings.

        Assume one per line."""

        for p in folium_dir.glob('**/*.py'):
            with p.open(encoding='UTF-8') as f:
                old_lines = f.readlines()
                upd_lines = [self.local_https(line) for line in old_lines]
                if upd_lines!=old_lines:
                    with p.open('w', newline='', encoding='UTF_8') as f:
                        f.writelines(upd_lines)

    def download_from_css(self, local_dir):
        """Inspect downloaded CSS files, find url() function calls, and update those."""

        for old_u, name in dict(self.url_map).items():
            if name.endswith('.css'):
                print(old_u)
                print(name)
                with (local_dir / name).open(encoding='UTF-8') as f:
                    text = ''.join(f.readlines())

                # Reverse the matches so the spans aren't altered.
                #
                matched = False
                for m in reversed(list(CSS_RE.finditer(text))):
                    # print(m)
                    b, e = m.span(1)
                    u2 = text[b:e]
                    if u2.startswith(('"', "'")):
                        b, e = b+1, e-1
                        u2 = text[b:e]

                    if (ix:=u2.find('?'))>=0:
                        # Remove IE8 fix.
                        #
                        u2 = u2[:ix-1]

                    if u2.startswith(('data:', '#', '%')):
                        # Inline data - don't do anything.
                        #
                        pass
                    else:
                        if u2.startswith('//'):
                            u2 = f'https:{u2}'
                        else:
                            u2 = url_relative(old_u, u2)

                        if u2 not in self.url_map:
                            name2 = url_to_name(u2)
                            download_file(u2, local_dir, name2)
                            self.url_map[u2] = name2

                        text = f'{text[:b]}{self.local_url}/{name2}{text[e:]}'

                        matched = True

                        print(u2)
                        print(name2)

                if matched:
                    with (local_dir / name).open('w', encoding='UTF-8') as f:
                        f.write(text)

                print()

    def download_from_py(self, local_dir):
        for old_u, name in self.url_map.items():
            print(f'{old_u}\n{name}\n')

            download_file(old_u, local_dir, name)

        self.download_from_css(local_dir)

        with open(local_dir / 'zzdownloaded.json', 'w', encoding='UTF-8') as f:
            json.dump(self.url_map, f, indent=2)

def download_file(u, local_dir, name):
    r = requests.get(u)
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
            print('Download directory {d} does not exist')
            sys.exit(3)

    repl_url = args.url

    um = UrlModifier(args.url)
    um.process_py(Path(args.dir))

    print(f'{args.download=}')
    if args.download:
        local_dir = Path(args.download)
        um.download_from_py(local_dir)
