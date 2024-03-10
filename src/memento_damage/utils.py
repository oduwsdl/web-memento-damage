from pathlib import Path
import validators
import re, os
from hashlib import md5
from urllib import parse

URI_BLACKLIST = [
    'https://analytics.archive.org/',
    'http://analytics.archive.org/',
    'https://web.archive.org/static',
    'http://web.archive.org/static',
    '[INTERNAL]',
    'data:'
]


def rootDir() -> Path:
    # PROJECT ROOT DIR / *** src *** / util / utils.py
    return Path(__file__).parent.parent.absolute()


def mkDir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)



def touch(path: str):
    return Path(path).touch(exist_ok=True)


def rmdir_recursive(d, exception_files=[]):
    for path in (os.path.join(d, f) for f in os.listdir(d)):
        if os.path.isdir(path):
            rmdir_recursive(path)
        else:
            remove = True
            for ef in exception_files:
                matches = re.findall(r'' + ef, path)
                if len(matches) > 0:
                    remove = False
                    break

            if remove:
                os.unlink(path)

    try:
        os.rmdir(d)
    except OSError as e:
        if e.errno != os.errno.ENOTEMPTY: pass


def uriToFoldername(uri: str) -> str:
    uri = unescapeUri(uri)
    if uri.endswith('/'):
        uri = uri[:-1]
    uri = uri \
        .replace('https', '') \
        .replace('http', '') \
        .replace('://', '') \
        .replace('.', '_') \
        .replace('/', '_') \
        .replace('~', '')
    uri = uri[0:200]
    return uri


def hashUri(uri: str) -> str:
    return md5(uri.encode()).hexdigest()


def escapeUri(uri: str) -> str:
    return parse.quote(uri)


def unescapeUri(uri: str) -> str:
    return parse.unquote(uri)


def validateURL(url: str) -> bool:
    return validators.url(url, public=True)


def rectifyURI(uri: str) -> str:
    # Reformat webrecorder.io URI to wbrc.io URI
    if uri.startswith('https://webrecorder.io') or uri.startswith('http://webrecorder.io'):
        wrc_comps = uri.replace('https://', '').replace('http://', '')
        wrc_comps = uri.replace('webrecorder.io/', '').split('/')
        user, project, date = wrc_comps[:3]
        wrc_url = '/'.join(wrc_comps[3:])
        uri = f'https://wbrc.io/{user}/{project}/{date}id_/{wrc_url}'

    # Set protocol to HTTP for Internet Archive targets
    elif uri.startswith('https://web.archive.org'):
        uri = uri.replace('https://web.archive.org', 'http://web.archive.org')

    iaUrlMatch = re.match((r'^(https?:\/\/web\.archive\.org\/web\/\d{14})\/(https?:\/\/.*)'), uri)
    if iaUrlMatch:
        uri = f'{iaUrlMatch.group(1)}if_/{iaUrlMatch.group(2)}'

    return uri


def rgb2hex(r, g, b) -> str:
    return f'{r:02x}{g:02x}{b:02x}'.upper()


def areaRectIntersect(a, b) -> float:
    dx = min(a.xmax, b.xmax) - max(a.xmin, b.xmin)
    dy = min(a.ymax, b.ymax) - max(a.ymin, b.ymin)
    if (dx >= 0) and (dy >= 0): return dx * dy


def dominantPixelPercentage(image):
    width, height = image.size
    detected_colors = {}

    for x in range(0, width):
        for y in range(0, height):
            r, g, b, _ = image.getpixel((x, y))
            rgb = f'{r} {g} {b}'
            if rgb in detected_colors:
                detected_colors[rgb] += 1
            else:
                detected_colors[rgb] = 1

    detected_colors = sorted(detected_colors.items(), key=lambda x:x[1], reverse=True)
    if len(detected_colors) > 0:
        return int(detected_colors[0][1]) / (int(width)*int(height))
    else:
        return 0.0