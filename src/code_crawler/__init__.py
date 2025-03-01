import argparse, csv, json, logging, re, requests, sys, time
from datetime import datetime
from pathlib import Path
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse

from memento_damage import utils
from code_crawler.code_crawler import IASourceCrawler


LOG_FILE = 'cli.log'
LOG_FORMAT = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
LOG_LEVEL = 30
log = None

REPO_HOSTS = ['github.com', 'gitlab.com', 'sourceforge.net']


def main():
    global LOG_LEVEL
    global log

    args = parseArgs()

    # Set log level from args
    if args.VERBOSE: LOG_LEVEL = logging.INFO
    if args.DEBUG: LOG_LEVEL = logging.DEBUG

    # Log initialization
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

    session = requests.Session()
    adapter = HTTPAdapter()
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    items = []

    if args.URI.startswith('file:'):
        uriFilePath = args.URI[5:]
        try:
            if not Path(uriFilePath).is_file() or not uriFilePath.endswith('.csv'):
                raise FileNotFoundError(f'Unable to find input file: {uriFilePath}')

            with open(uriFilePath, newline='') as csvFile:
                reader = csv.DictReader(csvFile, quoting=csv.QUOTE_MINIMAL)

                for row in reader:
                    items.append((
                        utils.rectifyURI(row['uri']),
                        row['branch'] if len(row['branch']) > 0 else None,
                        row['start'] if len(row['start']) > 0 else None,
                        row['end'] if len(row['end']) > 0 else None
                    ))

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

    else:
        branch = args.BRANCH
        uri = utils.rectifyURI(args.URI)
        items.append((uri, branch, args.CDX_START, args.CDX_END))

    for i in items:
        uriFolder = utils.uriToFoldername(i[0])
        uriCache = Path(args.CACHE, uriFolder).absolute()

        log.info(f'Crawling repo: {i[0]}')
        print(f'Crawling repo: {i[0]}')
        repoCrawler = IASourceCrawler(uriCache, session, i[0], i[1])

        skipped = repoCrawler.crawlSource()
        if not skipped:
            time.sleep(10)


def parseArgs():
    parser = argparse.ArgumentParser(
        prog='Memento Damage Source Evaluator',
        description='CLI utility for analysis of archived source trees',
        usage='%(prog)s [options] <URI>',
        epilog='oduwsdl.github.io (@WebSciDL)')

    parser.add_argument('-b', '--branch', dest='BRANCH',
                        required=False, default=None,
                        help='Set specified repository branch')
    parser.add_argument('-c', '--cache', dest='CACHE',
                        required=True,
                        help='Set specified cache path')
    parser.add_argument('-d', '--debug', dest='DEBUG',
                        action='store_true',
                        help='Enable debugging mode (default: off)')
    parser.add_argument('-e', '--end', dest='CDX_END',
                        required=False, default=None,
                        help='Ending timestamp for CDX retrieval')
    parser.add_argument('-s', '--start', dest='CDX_START',
                        required=False, default=None,
                        help='Ending timestamp for CDX retrieval')
    parser.add_argument('-t', '--timeout', dest='TIMEOUT',
                        type=int, choices=range(10, 600), default=30,
                        help='Crawl timeout (in seconds; 10 < t < 600; default: 30)')
    parser.add_argument('-V', '--verbose', dest='VERBOSE',
                        action='store_true',
                        help='Enable extended logging output')
    parser.add_argument('-v', '--version',
                        action='version', version='%(prog)s v0.1.0',
                        help='Display version information')
    parser.add_argument('URI',
                        help='Repository URI to analyze')

    args = parser.parse_args()

    if len(sys.argv) < 1:
        parser.print_help()
        exit(1)

    return args


if __name__ == '__main__':
    main()