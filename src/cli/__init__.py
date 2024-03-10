from pathlib import Path
import argparse, csv, logging
import re
import sys, time, json, requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from ratelimit import limits, sleep_and_retry
from urllib.parse import urlparse

from memento_damage import utils
from memento_damage.analysis import DamageAnalysis


# Default viewport size
VIEWPORT = (1920, 1080)

# Log parameters
LOG_FILE = 'cli.log'
LOG_FORMAT = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
LOG_LEVEL = 30
log = None

# Network adapter
session = requests.Session()
# retry = Retry(connect=0, redirect=10, backoff_factor=10, backoff_jitter= respect_retry_after_header=True)
adapter = HTTPAdapter()
session.mount('http://', adapter)
session.mount('https://', adapter)

# Work queues
dereferenceQueue = []
crawlQueue = []

MAX_URI_RETRIES = 2

lastIACrawlCompleted = None
iaRefusedCount = 0
iaRefusedBackoffSeconds = [60, 300, 600]
iaCrawlsSinceLastRefusal = 0

'''
Command-line main entry
'''
def main():
    global LOG_LEVEL
    global log
    global MAX_URI_RETRIES

    args = parseArgs()

    # Set log level from args
    if args.VERBOSE: LOG_LEVEL = logging.INFO
    if args.DEBUG: LOG_LEVEL = logging.DEBUG

    '''
    Log initialization
    '''
    try:
        utils.mkDir(args.CACHE)

        # Initialize server log file
        # logMode = 'a' if Path(cacheDir, LOG_FILE).is_file() and not args.IGNORE_CACHE else 'w'
        logMode = 'a'
        fileHandler = logging.FileHandler(Path(args.CACHE, LOG_FILE), mode=logMode)
        fileHandler.setFormatter(LOG_FORMAT)
        log = logging.getLogger('cli')
        log.addHandler(fileHandler)
        log.setLevel(LOG_LEVEL)
        log.info('Server initialized')
    except:
        print('FATAL: Unable to initialize server cache')
        exit(1)


    '''
    Process input URIs
    '''
    items = []

    if args.DEBUG: print('Processing input URIs')

    # Multiple URI mode
    # If -w or --warc is present, they will be ignored in favor of input file
    if args.URI.startswith('file:'):
        uriFilePath = args.URI[5:]
        try:
            if not Path(uriFilePath).is_file() or not uriFilePath.endswith('.csv'):
                raise FileNotFoundError(f'Unable to find input file: {uriFilePath}')

            with open(uriFilePath, newline='') as csvFile:
                csvUrls = list(csv.reader(csvFile, delimiter=','))
                cols = len(csvUrls[0])

                for row in csvUrls:
                    try:
                        uri = row[0]
                        warcFile = row[1] if (cols > 1 and len(row[1]) and (row[1].endswith('.wacz') or row[1].endswith('.warc'))) else None
                        result = urlparse(uri)
                        if not (result.scheme and result.netloc):
                            log.error(f'Skipping invalid URL: {uri}')
                            continue

                        if warcFile == None: uri = utils.rectifyURI(uri)
                        items.append((uri, warcFile))
                    except Exception as e:
                        print(e)
                        raise ValueError(f'Unable to parse row: {row}')

            log.info(f'Input file loaded: {uriFilePath}')
        except (FileNotFoundError, ValueError) as e:
            if args.DEBUG: print(e)
            log.error(e)
            exit(1)
        except Exception as e:
            if args.DEBUG: print(f'Unable to parse input file: {uriFilePath}')
            log.error(f'Unable to parse input file: {uriFilePath}')
            log.error(e)
            exit(1)

    # Single URI
    else:
        warcFile = args.WARC if args.WARC and (args.WARC.endswith('.wacz') or args.WARC.endswith('.warc')) else None

        uri = args.URI
        result = urlparse(uri)
        if not (result.scheme and result.netloc):
            log.error(f'Skipping invalid URL: {uri}')
            exit(1)

        if warcFile == None: uri = utils.rectifyURI(uri)
        items.append((uri, warcFile))


    '''
    Enqueue jobs
    '''
    for item in items:
        uri, warc = item[0], item[1]

        if warc:
            if warc.startswith('http://') or warc.startswith('https://'):
                uriFolder = f'[{utils.uriToFoldername(warc)}]_{utils.uriToFoldername(uri)}'
            else:
                if not args.WARC_DIR:
                    log.error(f'No directory specified for {warcFile}')
                    continue
                elif args.WARC_DIR and not Path(args.WARC_DIR, warc).is_file():
                    log.error(f'Archive not found at {Path(args.WARC_DIR, warc).absolute()}')
                    continue

                uriFolder = f'[{warc}]_{utils.uriToFoldername(uri)}'

            uriCache = Path(args.CACHE, uriFolder).absolute()
        else:
            uriFolder = utils.uriToFoldername(uri)
            uriCache = Path(args.CACHE, uriFolder).absolute()

        dereferenceQueue.append((uri, uriCache))

    if args.DEBUG: print(f'Enqueued {len(dereferenceQueue)} URIs for dereferencing')

    '''
    Dereference URIs
    '''
    if args.DEBUG: print('Dereferencing URIs')
    uriRetries = []
    while len(dereferenceQueue) > 0:
        uri, uriCache = dereferenceQueue.pop(0)

        if not Path(uriCache).is_dir():
            utils.mkDir(uriCache)
            with open(Path(uriCache, 'uri.json'), 'w') as f:
                json.dump({'original': uri}, f, indent=2)

        if Path(uriCache, 'uri.json').is_file():
            with open(Path(uriCache, 'uri.json'), 'r') as f:
                try:
                    j = json.load(f)
                    if 'dereference' in j:
                        dereferencedUri = j['dereference']
                        crawlQueue.append((dereferencedUri, uriCache))
                        continue
                except Exception as e:
                    log.error(e)
                    if args.DEBUG: print(e)
        else:
            if args.DEBUG: print(f'Unable to load cached URI data: {uri}')

        iaUrlMatch = re.match(r'^(https?:\/\/web\.archive\.org\/web\/\d{14}(if_)?\/)(https?:\/\/.*)', uri)
        if iaUrlMatch:
            with open(Path(uriCache, 'uri.json'), 'w') as f:
                json.dump({'original': uri, 'dereference': uri}, f, indent=2)
            crawlQueue.append((uri, uriCache))
            if args.DEBUG: print(f'Recorded direct IA URI dereference')
        else:
            if args.DEBUG: print(f'Dereferencing {uri}')
            dereferencedUri, status, error = dereferenceURI(uri)
            match status:
                case 200:
                    dereferencedUri = utils.rectifyURI(dereferencedUri)
                    with open(Path(uriCache, 'uri.json'), 'w') as f:
                        json.dump({'original': uri, 'dereference': dereferencedUri}, f, indent=2)
                    crawlQueue.append((dereferencedUri, uriCache))
                    log.info(f'Dereferenced URI: {dereferencedUri}')
                case 429:
                    if error == 'URI is actively being archived, try again later':
                        log.info(f'Recieved 429: URI is being archived, not requeuing')
                        with open(Path(uriCache, 'error.json'), 'w') as f:
                            json.dump({'error': error}, f, indent=2)
                    else:
                        uriRetries.append(uri)
                        numUriRetries = len(list(filter(lambda x: x == uri, uriRetries)))
                        if numUriRetries < MAX_URI_RETRIES:
                            log.info(f'Recieved 429: pausing for 30 seconds and requeuing {uri}')
                            dereferenceQueue.append((uri, uriCache))
                        else:
                            log.info(f'Recieved 429: pausing for 30 seconds, {uri} has reached max retries')
                            with open(Path(uriCache, 'error.json'), 'w') as f:
                                json.dump({'error': 'URI exeeded maxiumum dereference attempts ({uri})'}, f, indent=2)
                        time.sleep(30)
                case _:
                    log.error(f'Error dereferencing URI: {uri}')
                    with open(Path(uriCache, 'error.json'), 'w') as f:
                        json.dump({'error': error}, f, indent=2)


    '''
    Crawl dereferenced URIs
    '''
    while len(crawlQueue) > 0:
        uri, uriCache = crawlQueue.pop(0)
        checkDamage(args, uriCache, uri)


@sleep_and_retry
@limits(calls=1, period=6)
def dereferenceURI(uri, timeout=30):
    try:
        response = session.head(uri, allow_redirects=True, timeout=timeout, verify=False, headers={
            'User-Agent': 'URI dereferencer for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
        })

        if response.status_code == 404:
            return None, response.status_code, f'Page not found ({response.status_code}): {uri}'
        elif response.status_code == 429:
            if response.url.startswith('http://web.archive.org/save/_embed'):
                return response.url, response.status_code, f'URI is actively being archived, try again later'
            return None, response.status_code, f'Too many requests'
        else:
            return response.url, response.status_code, None
    except requests.exceptions.Timeout as e:
        return None, 408, f'Timeout error: {e}'
    except requests.exceptions.ConnectionError as e:
        return None, None, f'Connection error: {e}'
    except Exception as e:
        return None, None, f'Unable to dereference URI: {e}'


def checkDamage(args, uriCache, uri, warcDir=None, warcFile=None):
    global lastIACrawlCompleted
    global iaRefusedCount
    global iaCrawlsSinceLastRefusal
    global iaRefusedBackoffSeconds

    analysis = DamageAnalysis(uriCache, uri, warcDir, warcFile, options=(
        args.DEBUG,
        args.IGNORE_CACHE,
        LOG_LEVEL,
        args.TIMEOUT,
        VIEWPORT
    ))

    log.info(f'Checking damage for {uri}')
    if not analysis.isCrawled():
        iaUrlMatch = re.match(r'^https?:\/\/web\.archive\.org\/web\/', uri)
        if iaUrlMatch and lastIACrawlCompleted:
            secondsSinceLastIACrawl = (datetime.now() - lastIACrawlCompleted).seconds
            if secondsSinceLastIACrawl < 30:
                sleepTime = 30 - secondsSinceLastIACrawl
                if args.DEBUG: print(f'Self rate-limiting for {sleepTime} seconds')
                time.sleep(sleepTime)

        analysis.crawl(recrawl=args.RECRAWL)
        if iaUrlMatch:
            lastIACrawlCompleted = datetime.now()

            if not analysis.error and iaRefusedCount > 0:
                iaCrawlsSinceLastRefusal += 1
                if iaCrawlsSinceLastRefusal >= 3:
                    if args.DEBUG:
                        log.info(f'The Internet Archive seems to have forgiven our poor little roboto!')
                    iaCrawlsSinceLastRefusal = 0
                    iaRefusedCount = 0

            if analysis.error:
                if analysis.error == 'Network Error: Connection Refused':
                    # The Internet Archive has been angered! Best to wait a little while
                    iaRefusedCount += 1
                    iaCrawlsSinceLastRefusal = 0
                    if iaRefusedCount == 3:
                        log.error(f'Internet Archive has refused too many sequential connections, exiting')
                        exit(1)

                    log.warn(f'Connection refused by the Internet Archive, backing off and requeing: {uri}')
                    crawlQueue.append((uri, uriCache))
                    time.sleep(iaRefusedBackoffSeconds[iaRefusedCount-1])
                else:
                    log.error(f'Error crawling URI: {uri}\n{analysis.error}')
                    time.sleep(5)
                return

    score = analysis.damageScore()
    if score is None or args.IGNORE_CACHE:
        analysis.analyze()
        score = analysis.damageScore()

    if score is not None:
        log.info(f"{float(score)*100:.2f}% : {'['+warcFile+'] ' if warcFile else ''}{uri}")
        return
    else:
        log.error(f'Unable to calculate damage score for {uri}')


def parseArgs():
    parser = argparse.ArgumentParser(
        prog='Memento Damage CLI',
        description='CLI utility for analysis of Mementos and web pages',
        usage='%(prog)s [options] <URI>',
        epilog='oduwsdl.github.io (@WebSciDL)')

    parser.add_argument('-c', '--cache', dest='CACHE',
                        required=True,
                        help='Set specified cache path')
    parser.add_argument('-d', '--debug', dest='DEBUG',
                        action='store_true',
                        help='Enable debugging mode (default: off)')
    parser.add_argument('-i', '--ignore-cache', dest='IGNORE_CACHE',
                        action='store_true',
                        help='Ignore and overwrite existing cache data (default: off)')
    parser.add_argument('-r', '--recrawl', dest='RECRAWL',
                        action='store_true', default=False,
                        help='Force recrawl of Web page')
    parser.add_argument('-t', '--timeout', dest='TIMEOUT',
                        type=int, choices=range(10, 600), default=30,
                        help='Crawl timeout (in seconds; 10 < t < 600; default: 30)')
    parser.add_argument('-V', '--verbose', dest='VERBOSE',
                        action='store_true',
                        help='Enable extended logging output')
    parser.add_argument('-v', '--version',
                        action='version', version='%(prog)s v3.0.0',
                        help='Display version information')
    parser.add_argument('-w', '--warc', dest='WARC',
                        help='Local WARC/WACZ file name to process')
    parser.add_argument('-W', '--warc-dir', dest='WARC_DIR',
                        help='Directory for WARC files')
    parser.add_argument('URI',
                        help='URI to analyze')

    args = parser.parse_args()

    if len(sys.argv) < 1:
        parser.print_help()
        exit(1)

    return args


if __name__ == '__main__':
    main()