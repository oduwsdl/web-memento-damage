import csv, re, requests, logging, time, json, os
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from ratelimit import limits, sleep_and_retry

from memento_damage import utils


LOG_FILE = 'code_crawler.log'
LOG_FORMAT = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

BACKOFF_SECONDS = [60, 180, 300]

USER_AGENT_SUFFIX = 'Source code crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>'

GH_API_TOKEN = os.environ['GH_API_TOKEN']

timeout = 30


class IASourceCrawler():
    def __init__(self, cache, httpSession, uri, branch, startTimestamp=None, endTimestamp=None):
        self.httpSession = httpSession

        self.cache = cache
        self.archiveUri = uri
        self.repoUri, self.host, self.org, self.repoName = self.parseRepoInfo(self.archiveUri)
        self.branch = branch
        self.startTimestamp = startTimestamp
        self.endTimestamp = endTimestamp

        self.sourceMap = {}
        self.uriBacklog = []

        if not Path(self.cache).is_dir(): utils.mkDir(self.cache)

        self.fileHandler = logging.FileHandler(Path(self.cache, 'code_crawl.log'), mode='w')
        self.fileHandler.setFormatter(LOG_FORMAT)
        self._log = logging.getLogger(self.archiveUri)
        self._log.addHandler(self.fileHandler)
        self._log.setLevel(10)

        self.lastFileCrawlCompleted = datetime.now() - timedelta(seconds=30)
        self.lastDirCrawlCompleted = datetime.now() - timedelta(seconds=30)
        if (Path(self.cache, 'source_walk.jsonl').is_file()): Path(self.cache, 'source_walk.jsonl').unlink()

        self.starsCount = 0
        self.liveSourceTree = []
        self.archivedSourceTreeUnfiltered = []

        if Path(self.cache, 'source_original.csv').is_file():
            with open(Path(self.cache, 'source_original.csv'), 'r') as f:
                csvreader = csv.DictReader(f)
                for row in csvreader:
                    self.liveSourceTree.append(row['url'])
            self._log.info('Original source tree loaded from cache')
            # print('Original source tree loaded from cache')

        if Path(self.cache, 'source_cdx_unfiltered.csv').is_file():
            with open(Path(self.cache, 'source_cdx_unfiltered.csv'), 'r') as f:
                csvreader = csv.DictReader(f, quoting=csv.QUOTE_MINIMAL)
                for row in csvreader:
                    self.archivedSourceTreeUnfiltered.append([row["timestamp"], row["status"], row["url"]])
            self._log.info('Unfiltered archived source tree loaded from cache')
            # print('Unfiltered archived source tree loaded from cache')


    def updateSourceMap(self, node):
        with open(Path(self.cache, 'source_map.jsonl'), mode='a') as f:
            f.write(f'{json.dumps(node)}\n')


    def writeOriginalSourceTree(self):
        if Path(self.cache, 'source_original.csv').is_file(): return

        self._log.info(f'Writing GitHub source file')
        with open(Path(self.cache, 'source_original.csv'), 'w') as f:
            csvwriter = csv.writer(f)
            csvwriter.writerow(['url'])
            for r in self.liveSourceTree:
                csvwriter.writerow([r])


    def writeCDXResults(self, name, data):
        self._log.info(f'Writing source file: {name}')
        with open(Path(self.cache, f'{name}.csv'), 'w') as f:
            csvwriter = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            csvwriter.writerow(['timestamp', 'status', 'url'])
            for r in data:
                csvwriter.writerow(r)


    def parseRepoInfo(self, iaUri):
        iaRepoMatch = re.match(r'^(https?:\/\/web\.archive\.org\/web\/)(\d{14})(if_)?\/(https?:\/\/(www\.)?(github\.com|gitlab\.com|bitbucket\.org|sourceforge\.net)\/(.*)\/(.*))', iaUri)
        if iaRepoMatch:
            repoUri = iaRepoMatch.group(4)
            if repoUri[-1] == '/': repoUri = repoUri[:-1]
            return repoUri, iaRepoMatch.group(6), iaRepoMatch.group(7), iaRepoMatch.group(8)
        else:
            return None, None, None, None


    def getTimestamp(self, iaUri):
        iaRepoMatch = re.match(r'^(https?:\/\/web\.archive\.org\/web\/)(\d{14})(if_)?\/(https?:\/\/(www\.)?)(github\.com|gitlab\.com|bitbucket\.org|sourceforge\.net)\/(.*)', iaUri)
        if iaRepoMatch:
            return int(iaRepoMatch.group(2))
        else:
            return None


    def crawlSource(self):
        if self.host == 'github.com': self.getGitHubMetaInfo()

        if self.branch == None: self.branch = 'main'

        self.extractGitHubSourceTrees()
        # return not status

        self.sourceCompare()


    def getGitHubMetaInfo(self):
        repoInfoUri = f'http://api.github.com/repos/{self.org}/{self.repoName}'
        try:
            response = requests.get(repoInfoUri, headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {GH_API_TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28"
            })
        except requests.exceptions.Timeout as e:
            print(f'Timeout: {repoInfoUri}')
            return

        if response.status_code == 200:
            data = response.json()
            self.starsCount = data['watchers_count']
            if self.branch == None: self.branch = data['default_branch']
        else:
            print(f'Error retrieving data for GitHub repository: {repoInfoUri}')


    def walkSource(self, parentUri):
        status, parentUri, html = self.checkDirectory(parentUri)

        self.updateSourceMap({ 'type': 'directory', 'url': parentUri, 'status': status })

        if status != 200: return

        match self.host:
            case 'github.com':
                directories, files = self.extractLinksGitHub(parentUri, html)
            case 'gitlab.com':
                directories, files = self.extractLinksGitLab(parentUri, html)
            case 'sourceforge.net':
                directories, files = self.extractLinksSourceforge(parentUri, html)

        for uri in files:
            status, fileUri = self.checkFile(uri)
            self.updateSourceMap({ 'type': 'file', 'url': fileUri, 'status': status })

        for uri in directories:
            # secondsSinceLastIACrawl = (datetime.now() - self.lastIACrawlCompleted).seconds
            # if secondsSinceLastIACrawl < 30:
            #     sleepTime = 30 - secondsSinceLastIACrawl
            #     time.sleep(sleepTime)

            self.crawl(uri)


    def extractGitHubSourceTrees(self):
        if self.host != 'github.com':
            self._log.error('Invalid source: Comparison source must be GitHub repository')
            return False

        if not self.liveSourceTree:
            self._log.info('Retrieving live source tree')
            # print('Retrieving live source tree')
            self.retrieveLiveGitHubSourceTree()

        # if self.liveSourceTree:
        if self.liveSourceTree and not self.archivedSourceTreeUnfiltered:
            self._log.info('Retrieving archived source tree')
            # print('Retrieving archived source tree')
            self.retrieveArchivedCDXSourceTree()
            return True
        else:
            return False


    def sourceCompare(self):
        if not self.liveSourceTree and not self.archivedSourceTreeUnfiltered:
            with open(Path(self.cache, 'analysis.csv'), 'w') as f:
                csvwriter = csv.writer(f)
                csvwriter.writerow(['stars', 'archived_total_percent', 'archived_files_count', 'total_file_count', 'archived_dir_count', 'total_dir_count', 'f_0', 'f_1', 'f_2', 'f_3', 'f_4', 'f_5', 'd_0', 'd_1', 'd_2', 'd_3', 'd_4', 'd_5'])
                csvwriter.writerow([0, 0.0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            return

        # Analysis
        self._log.info('Comparing source code')
        # print('Comparing source code')

        archivedSourceFiltered = []

        compareList = []
        for url in self.liveSourceTree:
            m = re.match(r'^(https?)(.*)', url)
            u = m.group(2)
            u = u.lower()
            compareList.append(u)

        itemsIgnored = 0
        for item in self.archivedSourceTreeUnfiltered:
            m = re.match(r'^(https?)(.*)', item[2])
            u = m.group(2)
            u = u.lower()
            if u in compareList and int(item[1]) == 200:
                archivedSourceFiltered.append(item)
            elif u in compareList and int(item[1]) != 200:
                itemsIgnored += 1
                self._log.info(f'Item not archived: {item[2]}')
            else:
                itemsIgnored += 1
                self._log.info(f'Item not in source code: {item[2]}')

        self.writeCDXResults('source_cdx', archivedSourceFiltered)

        if itemsIgnored > 0:
            print(f'{itemsIgnored} source items ignored in comparison')


        pathDelimiter = f'/tree/{self.branch}/'
        fileDelimiter = f'/blob/{self.branch}/'

        archivedDirectories = [i[2] for i in archivedSourceFiltered if pathDelimiter in i[2]]
        archivedFiles = [i[2] for i in archivedSourceFiltered if fileDelimiter in i[2]]

        archivedFilesPerDepth = {}
        archivedDirsPerDepth = {}
        for url in archivedFiles:
            path = url.split(fileDelimiter)[1]
            depth = path.count('/')
            archivedFilesPerDepth[depth] = archivedFilesPerDepth.get(depth, 0) + 1
        for url in archivedDirectories:
            path = url.split(pathDelimiter)[1]
            depth = path.count('/')
            archivedDirsPerDepth[depth] = archivedDirsPerDepth.get(depth, 0) + 1

        allDirectories = [url for url in self.liveSourceTree if pathDelimiter in url]
        totalDirCount = len(allDirectories)
        allFiles = [url for url in self.liveSourceTree if fileDelimiter in url]
        totalFileCount = len(allFiles)

        totalFilesPerDepth = {}
        totalDirsPerDepth = {}
        for url in allFiles:
            path = url.split(fileDelimiter)[1]
            depth = path.count('/')
            totalFilesPerDepth[depth] = totalFilesPerDepth.get(depth, 0) + 1
        for url in allDirectories:
            path = url.split(pathDelimiter)[1]
            depth = path.count('/')
            totalDirsPerDepth[depth] = totalDirsPerDepth.get(depth, 0) + 1

        archivedFileCount = len(archivedFiles)
        archivedDirCount = len(archivedDirectories)
        if (totalDirCount + totalFileCount) == 0:
            archivedTotalPercent = 0.0
        else:
            archivedTotalPercent = float(archivedDirCount + archivedFileCount) / float(totalDirCount + totalFileCount)

        fX = [[], [], [], [], [], []]
        for d in totalFilesPerDepth.keys():
            if d > 5:
                fX[5].append(archivedFilesPerDepth.get(d, 0) / totalFilesPerDepth.get(d))
            else:
                fX[d].append(archivedFilesPerDepth.get(d, 0) / totalFilesPerDepth.get(d))
        for d in range(6):
            if len(fX[d]) > 0:
                fX[d] = sum(fX[d]) / len(fX[d])
            else:
                fX[d] = -1

        dX = [[], [], [], [], [], []]
        for d in totalDirsPerDepth.keys():
            if d > 5:
                dX[5].append(archivedDirsPerDepth.get(d, 0) / totalDirsPerDepth.get(d))
            else:
                dX[d].append(archivedDirsPerDepth.get(d, 0) / totalDirsPerDepth.get(d))
        for d in range(6):
            if len(dX[d]) > 0:
                dX[d] = sum(dX[d]) / len(dX[d])
            else:
                dX[d] = -1

        with open(Path(self.cache, 'analysis.csv'), 'w') as f:
            csvwriter = csv.writer(f)
            csvwriter.writerow(['stars', 'archived_total_percent', 'archived_files_count', 'total_file_count', 'archived_dir_count', 'total_dir_count', 'f_0', 'f_1', 'f_2', 'f_3', 'f_4', 'f_5', 'd_0', 'd_1', 'd_2', 'd_3', 'd_4', 'd_5'])
            csvwriter.writerow([self.starsCount, archivedTotalPercent, archivedFileCount, totalFileCount, archivedDirCount, totalDirCount, fX[0], fX[1], fX[2], fX[3], fX[4], fX[5], dX[0], dX[1], dX[2], dX[3], dX[4], dX[5]])

        print(f'Archived file percentage: {(float(archivedFileCount) / totalFileCount):.2f}')
        self._log.info(f'Archived file percentage: {(float(archivedFileCount) / totalFileCount):.2f}')


    @sleep_and_retry
    @limits(calls=1, period=6)
    def checkFile(self, uri):
        self._log.info(f'Checking {uri}')

        secondsSinceLastCrawl = (datetime.now() - self.lastFileCrawlCompleted).seconds
        if secondsSinceLastCrawl < 6:
            sleepTime = 6 - secondsSinceLastCrawl
            print('Sleeping 6 seconds for file check')
            time.sleep(sleepTime)

        try:
            response = self.httpSession.head(uri, allow_redirects=True, timeout=30, verify=False, headers={
                'User-Agent': 'Repository crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
            })

            self.lastFileCrawlCompleted = datetime.now()

            if response.status_code == 429:
                self._log.warn('Received 429 on file, pausing for 15 secs')
                time.sleep(15)
                response = self.httpSession.head(uri, allow_redirects=True, timeout=30, verify=False, headers={
                    'User-Agent': 'Repository crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
                })

                self.lastFileCrawlCompleted = datetime.now()

            return response.status_code, response.url
        except requests.exceptions.Timeout as e:
            self._log.error(f'Timeout: {uri}')
            self.lastFileCrawlCompleted = datetime.now()
            return 408, uri
        except requests.exceptions.ConnectionError as e:
            self._log.error(f'Connection refused: {uri}')
            self.lastFileCrawlCompleted = datetime.now()
            return 503, uri
        except Exception as e:
            self._log.error(f'Uncaught URI error: {uri}\n{e}')
            self.lastFileCrawlCompleted = datetime.now()
            return 418, uri


    @sleep_and_retry
    @limits(calls=1, period=30)
    def checkDirectory(self, uri):
        self._log.info(f'Checking {uri}')

        secondsSinceLastCrawl = (datetime.now() - self.lastDirCrawlCompleted).seconds
        if secondsSinceLastCrawl < 30:
            sleepTime = 30 - secondsSinceLastCrawl
            print('Sleeping 30 seconds for dir check')
            time.sleep(sleepTime)

        try:
            response = self.httpSession.get(uri, allow_redirects=True, timeout=30, verify=False, headers={
                'User-Agent': 'Repository crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
            })

            self.lastDirCrawlCompleted = datetime.now()

            html = None
            if response.status_code == 200:
                html = BeautifulSoup(response.content, 'html.parser')
            elif response.status_code == 429:
                self._log.warn('Received 429 on dir, pausing for 30 secs')
                time.sleep(30)
                response = self.httpSession.get(uri, allow_redirects=True, timeout=30, verify=False, headers={
                    'User-Agent': 'Repository crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
                })
                self.lastDirCrawlCompleted = datetime.now()
                if response.status_code == 200:
                    html = BeautifulSoup(response.content, 'html.parser')

            return response.status_code, response.url, html
        except requests.exceptions.Timeout as e:
            self._log.error(f'Timeout: {uri}')
            self.lastDirCrawlCompleted = datetime.now()
            return 408, uri, None
        except requests.exceptions.ConnectionError as e:
            self._log.error(f'Connection refused: {uri}')
            self.lastDirCrawlCompleted = datetime.now()
            return 503, uri, None
        except Exception as e:
            self._log.error(f'Uncaught URI error: {uri}\n{e}')
            self.lastDirCrawlCompleted = datetime.now()
            return 418, uri, None


    def retrieveLiveGitHubSourceTree(self):
        if self.liveSourceTree: return

        githubApiUri = f'https://api.github.com/repos/{self.org}/{self.repoName}/git/trees/{self.branch}?recursive=1'
        self._log.info(githubApiUri)

        try:
            response = requests.get(githubApiUri, headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {GH_API_TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28"
            })
        except requests.exceptions.Timeout as e:
            self._log.error(f'Timeout: {githubApiUri}')
            return

        if response.status_code == 200:
            sourceUris = []

            data = response.json()
            if data['truncated'] == True:
                print('Source tree exceeds 100,000 items and has been truncated!')
                self._log.warn('Source tree exceeds 100,000 items and has been truncated!')

            for item in data['tree']:
                path = item['path'].replace(' ', f'%20')
                itemType = item['type']
                uri = f'{self.repoUri}/{itemType}/{self.branch}/{path}'
                sourceUris.append(uri)

            for uri in sourceUris:
                self.liveSourceTree.append(uri)

            if len(self.liveSourceTree) > 0:
                self.writeOriginalSourceTree()
        else:
            print(f'Error retrieving source files\n{response.text}')
            self._log.error(f'Error retrieving source files\n{response.text}')


    def retrieveArchivedCDXSourceTree(self):
        # if self.archivedSourceTreeUnfiltered: return

        cdxPrefix = 'http://web.archive.org/cdx/search/cdx?matchType=prefix&output=json&fl=timestamp,statuscode,original&filter=mimetype:text/html&collapse=urlkey'
        cdxFileUri = cdxPrefix
        cdxRawFileUri = cdxPrefix
        cdxDirectoryUri = cdxPrefix

        if self.startTimestamp:
            cdxFileUri += f'from={self.startTimestamp}'
            cdxRawFileUri += f'from={self.startTimestamp}'
            cdxDirectoryUri += f'from={self.endTimestamp}'
        if self.endTimestamp:
            cdxFileUri += f'to={self.endTimestamp}'
            cdxRawFileUri += f'to={self.endTimestamp}'
            cdxDirectoryUri += f'to={self.endTimestamp}'

        cdxFileUri += f'&url={self.repoUri}/blob/{self.branch}'
        cdxDirectoryUri += f'&url={self.repoUri}/tree/{self.branch}'
        cdxRawFileUri += f'&url=https://raw.githubusercontent.com/{self.org}/{self.repoName}/refs/heads/{self.branch}'

        files = []
        rawFiles = []
        directories = []
        unfilteredItems = []

        # self._log.info(cdxDirectoryUri)
        # response = requests.get(cdxDirectoryUri, timeout=30, verify=False, headers={
        #     'User-Agent': 'Repository crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
        # })
        # if response.status_code == 200:
        #     resJson = response.json()
        #     directories = resJson[1:]

        #     for d in directories:
        #         unfilteredItems.append(d)
        # else:
        #     print(f'Error retrieving CDX directories:\n{response.text}')
        #     self._log.error(f'Error retrieving CDX directories:\n{response.text}')

        # time.sleep(6) # artificial delay for rate-limiting

        self._log.info(cdxFileUri)
        try:
            response = requests.get(cdxFileUri, timeout=30, verify=False, headers={
                'User-Agent': 'Repository crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
            })
        except requests.exceptions.Timeout as e:
            self._log.error(f'Timeout: {cdxFileUri}')
            return

        if response.status_code == 200:
            resJson = response.json()
            files = resJson[1:]

            for f in files:
                unfilteredItems.append(f)
        else:
            print(f'Error retrieving CDX files:\n{response.text}')
            self._log.error(f'Error retrieving CDX files:\n{response.text}')

        if unfilteredItems:
            self.writeCDXResults('source_cdx_unfiltered', unfilteredItems)
            self.archivedSourceTreeUnfiltered = unfilteredItems

        # time.sleep(6)

        # self._log.info(cdxRawFileUri)
        # try:
        #     response = requests.get(cdxRawFileUri, timeout=30, verify=False, headers={
        #         'User-Agent': 'Repository crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
        #     })
        # except requests.exceptions.Timeout as e:
        #     self._log.error(f'Timeout: {cdxFileUri}')
        #     return

        # if response.status_code == 200:
        #     resJson = response.json()
        #     files = resJson[1:]

        #     for f in files:
        #         rawFiles.append(f)
        # else:
        #     print(f'Error retrieving CDX files:\n{response.text}')
        #     self._log.error(f'Error retrieving CDX files:\n{response.text}')

        # if rawFiles:
        #     print(f'Retrieved {len(rawFiles)} raw files: {cdxRawFileUri}')
        #     self.writeCDXResults('source_cdx_raw', rawFiles)



    # def crawlIssues(self, org, repo):
    #     '''
    #     - Archive issue URIs will be REPO/issues/:num
    #     - :num can be any type of issue, such as actual issues, merge requests, test results, etc.
    #     - graphql api can get issuecount
    #     '''
    #     issueCount = None

    #     # Get issue count
    #     githubApiIssueCountUri = f"https://api.github.com/repos/{org}/{repo}/issues?state=all&per_page=1&page=1"
    #     issueCountRes = requests.get(githubApiIssueCountUri, headers={
    #         "Accept": "application/vnd.github+json",
    #         "Authorization": "Bearer {GH_API_TOKEN}",
    #         "X-GitHub-Api-Version": "2022-11-28"
    #     })
    #     if issueCountRes.status_code == 200:
    #         resJson = issueCountRes.json()
    #         issueCount = resJson[0]['number']

    #     # Check archived issue URIs
    #     cdxIssueUri = 'http://web.archive.org/cdx/search/cdx?matchType=prefix&output=json&fl=timestamp,statuscode,original&collapse=urlkey' \
    #         + f'&url=github.com/{org}/{repo}/issues'
    #     cdxRes = requests.get(cdxIssueUri, timeout=30, verify=False, headers={
    #         'User-Agent': 'Repository crawler for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
    #     })


    def extractLinksGitHub(self, parentUri, html):
        directories, files = [], []

        timestamp = self.getTimestamp(parentUri)
        if timestamp == None:
            return directories, files

        # TODO: Check all ISA archive years for proper link selector strings
        if timestamp >= 20230000000000:
            linksSelector = 'table[aria-labelledby="folders-and-files"] > tbody > tr > td > div > div > h3 > div > a'
        elif timestamp >= 20220000000000:
            linksSelector = 'div[role="grid"][aria-labelledby="files"] > div[role="row"][class*="Box-row"] > div[role="rowheader"] > span > a'
        elif timestamp >= 20150000000000:
            linksSelector = 'table[class*="files"] > tbody > tr > td[class="content"] > span > a'

        links = html.select(linksSelector)
        hrefs = list(set([l.get('href') for l in links]))

        for href in hrefs:
            url = f'http://web.archive.org{href}'

            if re.search(r'\/tree\/.*\/', href):
                directories.append(url)
            elif re.search(r'\/blob\/.*\/', href):
                files.append(url)

        return directories, files


    def extractLinksGitLab(self, parentUri, html):
        directories, files = [], []

        linksSelector = 'table > tbody > tr[class="tree-item"] > td[class*="tree-item-file-name"] > a'

        links = html.select(linksSelector)
        hrefs = [l.get('href') for l in links]

        for href in hrefs:
            url = f'http://web.archive.org{href}'

            if re.search(r'(\/\-)?\/tree\/.*\/', href):
                directories.append(url)
            elif re.search(r'(\/\-)?\/blob\/.*\/', href):
                files.append(url)

        return directories, files


    def extractLinksSourceforge(self, parentUri, html):
        directories, files = [], []

        timestamp = self.getTimestamp(parentUri)
        if timestamp == None:
            return directories, files

        # TODO: Check all ISA archive years for proper link selector strings
        linksSelector = 'table > tbody > tr > td:nth-of-type(1) > a'

        links = html.select(linksSelector)

        for link in links:
            href = link.get('href')

            folderIcon = None
            fileIcon = None
            if timestamp >= 20160000000000:
                folderIcon = link.select_one('i[class*="fa-folder"]')
                fileIcon = link.select_one('i[class*="fa-file-o"]')
            elif timestamp >= 20130000000000:
                folderIcon = link.select_one('b[class*="folder"]')
                fileIcon = link.select_one('b[class*="table"]')

            if folderIcon is not None:
                directories.append(f'{parentUri}{href}')
            elif fileIcon is not None:
                files.append(f'{parentUri}{href}')
            else:
                self._log.error(f'Unknown item: {parentUri}{href}')

        return directories, files
