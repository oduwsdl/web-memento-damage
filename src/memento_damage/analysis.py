import logging, json, os, re, urllib3, hashlib, shutil
import numpy as np
from collections import namedtuple
from pathlib import Path
from PIL import Image, ImageDraw
from subprocess import run

from .constants import EMOJI_NAMES
from . import utils

MEMGATOR_HOST = 'https://memgator.cs.odu.edu'

LOG_FORMAT = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
CRAWL_SCRIPT = Path(utils.rootDir(), 'crawler', 'crawler.js')
CRAWL_DATA_FILES = [
    'css.jsonl',
    'js.jsonl',
    'iframe.jsonl',
    'text.jsonl',
    'image.jsonl',
    'media.jsonl',
]
NETWORK_FILES = [
    'requests.jsonl',
    'requests_failed.jsonl',
    'requests_pending.jsonl',
    'responses.jsonl',
    'redirects.jsonl',
]

Rectangle = namedtuple('Rectangle', 'xmin ymin xmax ymax')

VIEWPORT_SIZE = (1920, 1080)

# Augmented image sizes
S_EMOJI = (32, 32)
S_AVATAR = (50, 50)
S_THUMBNAIL = (150, 150)
S_IMAGE_SM = (300, 200)
S_IMAGE_LG = (500, 400)
S_VIDEO_SM = (854, 480)
S_VIDEO_LG = (1280, 720)

# Category weights
W_CSS = 0.1
W_JS = 0.1
W_TEXT = 0.1
W_IMAGE = 0.3
W_VIDEO = 0.4

# WORD_IMG_RATIO = 1000

URI_BLACKLIST = [
    'https://analytics.archive.org/',
    'http://analytics.archive.org/',
    'https://web.archive.org/static',
    'http://web.archive.org/static',
    # '[INTERNAL]',
]


class DamageAnalysis:

    def __init__(self, cacheDir, uri, warcDir=None, warcFile=None, options=None):
        self.debug, \
        self.ignoreCache, \
        self.logLevel, \
        self.timeout, \
        self.viewport = options if options else (False, False, logging.WARN, 30, (1920, 1080))

        self._log = None

        self.uri: str = uri
        self.warcDir = warcDir
        self.warcFile = warcFile
        self.cacheDir: str = cacheDir

        self.error = None
        self.result = None
        self._template = None

        self._netData = None
        self._crawlData = None
        self._pageData = None
        self._precursors = None
        # self._redirectMap = None
        # self._urirRedirects = None

        self.potentialDamage = {
            'media': [],
            'iframe': [],
            'image': [],
            'text': [],
            'css': [],
            'js': [],
        }
        self.actualDamage = {
            'media': [],
            'iframe': [],
            'image': [],
            'text': [],
            'css': [],
            'js': [],
        }

        self._annotations = {}

        # Initialize cache and logging
        if not Path(self.cacheDir).is_dir():
            # if self.debug: print(f'Creating cache subdirectory: {self.cacheDir}')
            utils.mkDir(self.cacheDir)

        logMode = 'a' if Path(self.cacheDir, 'analysis.log').is_file() and not self.ignoreCache else 'w'
        fileHandler = logging.FileHandler(Path(self.cacheDir, 'analysis.log'), mode=logMode)
        fileHandler.setFormatter(LOG_FORMAT)
        self._log = logging.getLogger(self.uri)
        self._log.addHandler(fileHandler)
        self._log.setLevel(self.logLevel)

        self._loadTemplate()
        self._loadCachedData()


    def _closeLog(self) -> None:
        for h in self.logger.handlers:
            h.flush()
            h.close()
            self.logger.removeHandler(h)


    def _loadCachedData(self) -> None:
        self._log.info('Loading cached data')

        # Check for error file
        if Path(self.cacheDir, 'error.json').is_file():
            with open(Path(self.cacheDir, 'error.json'), 'r') as errFile:
                errorMessage = json.load(errFile)
                self.error = errorMessage['error']

        # Network files
        try:
            netPath = Path(self.cacheDir, 'net')
            if netPath.is_dir() and any(f.is_file() for f in netPath.rglob("*")):
                self._netData = {}
                for netFile in NETWORK_FILES:
                    if not Path(self.cacheDir, 'net', netFile).is_file(): continue
                    with open(Path(self.cacheDir, 'net', netFile), mode='r', encoding='utf-8') as f:
                        self._netData[netFile[:-len('.jsonl')]] = [json.loads(line) for line in list(f)]
        except Exception as e:
            print(e)
            self._netData = None

        # Data files
        try:
            dataPath = Path(self.cacheDir, 'data')
            if dataPath.is_dir() and any(f.is_file() for f in dataPath.rglob("*")):
                self._crawlData = {}
                for dataFile in CRAWL_DATA_FILES:
                    if not Path(self.cacheDir, 'data', dataFile).is_file(): continue
                    with open(Path(self.cacheDir, 'data', dataFile), mode='r', encoding='utf-8') as f:
                        self._crawlData[dataFile[:-len('.jsonl')]] = [json.loads(line) for line in list(f)]
        except Exception as e:
            print(e)
            self._crawlData = None

        # Existing analysis data
        try:
            if Path(self.cacheDir, 'result.json').is_file():
                with open(Path(self.cacheDir, 'result.json'), mode='r', encoding='utf-8') as f:
                    self.result = json.loads(f.read())
            else:
                self.result = None
        except Exception as e:
            print(e)
            self._log.error(f'Unable to load result data')
            self.result = None


    def _clearAnalysisData(self) -> None:
        # Result file
        try:
            if Path(self.cacheDir, 'data', 'precursors.jsonl').is_file():
                Path(self.cacheDir, 'data', 'precursors.jsonl').unlink()
        except Exception as e:
            print(e)
        finally:
            self._precursors = None

        # Result file
        try:
            if Path(self.cacheDir, 'result.json').is_file():
                Path(self.cacheDir, 'result.json').unlink()
        except Exception as e:
            print(e)
        finally:
            self.result = None


    def _clearCachedData(self) -> None:
        self._log.info('Clearing data cache')

        self._clearError()

        # Network files
        try:
            if Path(self.cacheDir, 'net').is_dir():
                shutil.rmtree(Path(self.cacheDir, 'net'))
        except Exception as e:
            print(e)
        finally:
            self._netData = None

        # Data files
        try:
            if Path(self.cacheDir, 'data').is_dir():
                shutil.rmtree(Path(self.cacheDir, 'data'))
        except Exception as e:
            print(e)
        finally:
            self._crawlData = None

        # Page files
        try:
            if Path(self.cacheDir, 'page').is_dir():
                shutil.rmtree(Path(self.cacheDir, 'page'))
        except Exception as e:
            print(e)
        finally:
            self._pageData = None

        # Screenshots
        try:
            if Path(self.cacheDir, 'screenshots').is_dir():
                shutil.rmtree(Path(self.cacheDir, 'screenshots'))
        except Exception as e:
            print(e)

        # Result file (precursors data cleared when data dir was removed)
        try:
            if Path(self.cacheDir, 'result.json').is_file():
                Path(self.cacheDir, 'result.json').unlink()
        except Exception as e:
            print(e)
        finally:
            self.result = None


    def damageScore(self) -> tuple[float, str]:
        return self.result['total_damage'] if self.result else None


    def analyze(self) -> None:
        if self.result:
            if not self.ignoreCache:
                self._log.info('Existing analysis results')
                return
            else:
                self._clearAnalysisData()

        self._log.info(f'Beginning analysis for {self.uri}')

        self._log.info('Processing network logs')
        self._purgeBlacklistedURLs()
        self._purgeHiddenElements()

        self._log.info('Assessing page damage')
        self._calculatePageMetrics()
        if not self._pageData: return

        # Element breakdown
        numCodeElements = len(self._crawlData['css']) + len(self._crawlData['js'])
        numVisualElements = len(self._crawlData['iframe']) + len(self._crawlData['text']) + len(self._crawlData['image']) + len(self._crawlData['media'])
        totalElements = numCodeElements + numVisualElements
        totalElements = totalElements if totalElements > 0 else 1
        codeRatio = numCodeElements / totalElements
        visualRatio = numVisualElements / totalElements

        styleRules = sum([len(css['rules']) for css in self._crawlData['css']])

        self._precursors = {}
        for k in ['css', 'js', 'iframe', 'text', 'image', 'media']:
            self._precursors[k] = {}

        self._calculateStylesheetMetrics()
        self._calculateJavascriptMetrics()

        self._calculateIFrameMetrics()
        self._calculateTextMetrics()
        self._calculateImageMetrics()
        self._calculateMediaMetrics()

        self._calculateLocationMultipliers()
        self._calculateSemanticMultipliers()

        self._calculatePageDamageScore()

        self._generateAnnotatedScreenshot(generate_highlights=True)
        self._clearError()


    def isCrawled(self) -> bool:
        return self._crawlData is not None


    def crawl(self, recrawl=False) -> None:
        if self._crawlData and not recrawl:
            self._log.info('Existing crawl data, skipping...')
            return
        else:
            self._clearCachedData()

        crawlCommand = ['node', str(CRAWL_SCRIPT)]
        if self.debug: crawlCommand.append('-d')
        crawlCommand.append(f'--cache={str(self.cacheDir)}')
        crawlCommand.append(f'--log={str(self.logLevel)}')
        crawlCommand.append(f'--timeout={str(self.timeout)}')
        crawlCommand.append(f'--viewport={self.viewport[0]}_{self.viewport[1]}')
        if self.warcFile and self.warcDir:
            crawlCommand.append(f'--warcDir={str(self.warcDir)}')
            crawlCommand.append(f'--warcFile={str(self.warcFile)}')
        crawlCommand.append(self.uri)

        crawlProcess = run(crawlCommand)

        if crawlProcess.returncode > 0:
            self._log.error('Crawl unsuccessful (refer to crawl.log and error.json), skipping analysis...')
            if Path(self.cacheDir, 'error.json').is_file():
                with open(Path(self.cacheDir, 'error.json'), 'r') as errFile:
                    errorMessage = json.load(errFile)
                    self.error = errorMessage['error']
            return
        else:
            self._log.info('Crawl completed')
            self._loadCachedData()
            self._clearError()


    def _generateAnnotatedScreenshot(self, generate_highlights=False) -> None:
        if not Path(self.cacheDir, 'screenshots', 'screenshot.png').is_file():
            self._log.error('Unable to generate annotated screenshot, no base screenshot available.')
            return

        if len(self._annotations) > 0:
            screenshot = Image.open(Path(self.cacheDir, 'screenshots', 'screenshot.png'))
            annotatedScreenshot = ImageDraw.Draw(screenshot)

            if generate_highlights:
                utils.mkDir(Path(self.cacheDir, 'screenshots', 'highlights'))

            for group in self._annotations:
                for i in self._annotations[group]:
                    for ri, bbox in enumerate(self._annotations[group][i]['bbox']):
                        annotatedScreenshot.rectangle(
                            xy=(bbox['left'], bbox['top'], bbox['right'], bbox['bottom']),
                            outline='red',
                            width=2
                        )

                        textPosition = (bbox['left']+4, bbox['top'], bbox['right'], bbox['bottom'])
                        annotatedScreenshot.text(textPosition, f"{self._precursors[group][i]['value']*100*100:.2f}%", font_size=15,
                                                fill='white', stroke_width=1, stroke_fill='black')

                        if generate_highlights:
                            width, height = screenshot.size
                            buffer = 50
                            left = 0 if bbox['left']-buffer < 0 else bbox['left']-buffer
                            top = 0 if bbox['top']-buffer < 0 else bbox['top']-buffer
                            right = width if bbox['right']+buffer > width else bbox['right']+buffer
                            bottom = height if bbox['bottom']+buffer > height else bbox['bottom']+buffer

                            crop = screenshot.crop((left, top, right, bottom))
                            cropAnnotation = ImageDraw.Draw(crop)
                            cropAnnotation.rectangle(((left, top), (right, bottom)), fill=None, outline="red", width=3)
                            fileHash = hashlib.md5(f'{self._annotations[group][i]['imgUrl']}_{ri}'.encode())
                            crop.save(Path(self.cacheDir, 'screenshots', 'highlights', f'{fileHash.hexdigest()}.png'))

            screenshot.save(Path(self.cacheDir, 'screenshots', 'annotation.png'))
            screenshot.close()


    def _loadTemplate(self) -> None:
        uri = self.uri
        uri = uri[uri.rfind('://')+3:] if uri.rfind('://') > -1 else uri

        templatesCache = Path((Path(self.cacheDir).parent), 'templates')
        if templatesCache.is_dir():
            self._log.info('Loading templates...')
            legalTemplateKeys = ['contentArea', 'zones', 'selectors']
            for tFileName in os.listdir(templatesCache.absolute()):
                with open(Path(templatesCache, tFileName), 'r', encoding='utf-8') as tFile:
                    template = json.load(tFile)
                    try:
                        if 'urlRegex' not in template.keys() or any(not k in legalTemplateKeys for k in template.keys()):
                            raise ValueError("Template contains invalid root keys")

                        urlRegex = template['urlRegex']
                        if re.match(urlRegex, uri):
                            # Matching template found, validate content
                            if 'contentArea' in template:
                                if len(template['contentArea']) != 4 or (sorted(['t', 'b', 'l', 'r']) != sorted(template['contentArea'].keys())):
                                    raise ValueError("Invalid boundary key found for template 'contentArea'")
                                if any(type(v) != int or v < -1 for v in template['contentArea'].values()):
                                    raise ValueError("Invalid boundary value found for template 'contentArea'")

                            if 'zones' in template:
                                for i, zone in enumerate(template['zones']):
                                    if len(zone) != 5 or (sorted(['t', 'b', 'l', 'r', 'multiplier']) != sorted(zone.keys())):
                                        raise ValueError("Invalid keys found for template 'contentArea'")
                                    if any(k != 'multiplier' and (type(v) != int or v < -1) for k, v in zone.items()):
                                        raise ValueError(f'Invalid boundary value for template zone {i}')
                                    if (type(zone['multiplier']) != int or type(zone['multiplier']) != float) and zone['multiplier'] < 0.0:
                                        raise ValueError(f'Invalid multiplier value for template zone {i}')

                            if 'selectors' in template:
                                pass

                            self._log.info(f'Template applied: {tFileName}')
                            self._template = template
                            return
                    except ValueError as e:
                        self._log.error(f'Error parsing template: {e}')


    def _isMissing(self, url) -> bool:
        networkMatch = list(filter(lambda nRes: nRes['response']['url'].lower().endswith(url.lower()) and nRes['response']['status'] not in [301, 302, 303, 307, 308],
                                                self._netData['responses']))
        return True if networkMatch and networkMatch[0]['response']['status'] != 200 else False


    def _purgeBlacklistedURLs(self) -> None:
        def _isBlacklisted(url):
            if any(map(lambda blacklistedURI: url.startswith(blacklistedURI), URI_BLACKLIST)): return True

            # If not defined, check whether uri has header 'Link' containing <http://mementoweb.org/terms/donotnegotiate>; rel="type"
            # if url in self._netData['responses']:
            #     log = netData['response'][url]
            #     if 'headers' in log and 'link' in log['headers']:
            #         if log['headers']['link'] == '<http://mementoweb.org/terms/donotnegotiate>; rel="type"':
            #             return True
            return False

        if not self._crawlData: return
        for key in ['css', 'image', 'media', 'iframe']:
            filteredData = list(filter(lambda l: 'url' in l and not _isBlacklisted(l['url']), self._crawlData[key]))
            self._crawlData[key] = filteredData


    def _purgeHiddenElements(self) -> None:
        for key in ['text', 'image', 'media']:
            filteredData = list(filter(lambda i: 'visible' in i and i['visible'], self._crawlData[key]))
            self._crawlData[key] = filteredData


    def _calculatePageMetrics(self) -> None:
        self._log.info('Calculating page metrics')

        try:
            if not Path(self.cacheDir, 'screenshots', 'screenshot.png').is_file():
                if self.debug: print('Unable to load screenshot file')
                raise Exception('Unable to load screenshot file')

            screenshot = Image.open(Path(self.cacheDir, 'screenshots', 'screenshot.png'))

            pixelArray = np.array(screenshot.convert('L'))

            blackPixels = (pixelArray < 255).astype(np.uint8)
            columnPixels = blackPixels.sum(axis=0)
            rowPixels = blackPixels.sum(axis=1)

            self._pageData = {}
            self._pageData['page'] = {
                'width': screenshot.size[0],
                'height': screenshot.size[1],
                'heatmap_x': columnPixels.tolist(),
                'heatmap_y': rowPixels.tolist()
            }

            if self._template and 'contentArea' in self._template:
                tContentArea = self._template['contentArea']
                self._pageData['content'] = {
                    'left': tContentArea['left'], 'right': tContentArea['right'],
                    'top': tContentArea['top'], 'bottom': tContentArea['bottom'],
                    'width': tContentArea['width'], 'height': tContentArea['height']
                }
            else:
                content = np.where(blackPixels == np.amax(blackPixels))
                left, top = np.min(content[1]), np.min(content[0])
                right, bottom = np.max(content[1]), np.max(content[0])
                width, height = right-left, bottom-top
                self._pageData['content'] = {
                    'left': left, 'right': right,
                    'top': top, 'bottom': bottom,
                    'width': width, 'height': height
                }

            screenshot.close()
        except:
            self._log.error('Unable to calculate page metrics.', exc_info=True)
            self._pageData = None


    def _calculateJavascriptMetrics(self) -> tuple:
        self._log.info('Assessing JavaScript damage...')

        jsByteMap = []
        if Path(self.cacheDir, 'data', 'jsByteMap.jsonl').is_file():
            with open(Path(self.cacheDir, 'data', 'jsByteMap.jsonl'), mode='r', encoding='utf-8') as f:
                jsByteMap = [json.loads(line) for line in list(f)]
        else:
            self._log.info(f'No byte data available')

        for i, js in enumerate(self._crawlData['js']):
            self._precursors['js'][i] = {}

            if 'url' in js and self._isMissing(js['url']): self._precursors['js'][i]['missing'] = True

            self._precursors['js'][i]['metrics'] = {
                'usedBytes': 0,
                'totalBytes': 0
            }
            self._precursors['js'][i]['multipliers'] = {
                'net': 1.0
            }

            jsBytes = list(filter(lambda j: j['url'].endswith(js['url']), jsByteMap))
            # print(f"Checking bytemap for {js['url']}")
            if len(jsBytes) > 0:
                jsBytes = jsBytes[0]
                self._precursors['js'][i]['metrics'].update({'usedBytes': jsBytes['usedBytes'], 'totalBytes': jsBytes['totalBytes']})


    def _calculateStylesheetMetrics(self) -> tuple:
        self._log.info('Assessing stylesheet damage')

        # Element locations (all along left?)
        elementPlacementLeftDominant = False

        # Pixel distribution
        p3 = int(len(self._pageData['page']['heatmap_x']) / 3)
        total = np.sum(self._pageData['page']['heatmap_x'])
        total = total if total > 0 else 1
        left = np.sum(self._pageData['page']['heatmap_x'][0:p3]) / total
        center = np.sum(self._pageData['page']['heatmap_x'][p3:p3*2]) / total
        right = np.sum(self._pageData['page']['heatmap_x'][p3*2:]) / total

        # print(f'Pixel distribution: {left:.3f} {center:.3f} {right:.3f}')
        if left > 0.7 and (left > center and center > right) or elementPlacementLeftDominant:
            self._log.info('Primary stylesheet is potentially damaged or missing')

        if total == 0:
            heatmapRatio = 0.0
        else:
            heatmapRatio = max(left, center, right)

        cssByteMap = []
        if Path(self.cacheDir, 'data', 'cssByteMap.jsonl').is_file():
            with open(Path(self.cacheDir, 'data', 'cssByteMap.jsonl'), mode='r', encoding='utf-8') as f:
                cssByteMap = [json.loads(line) for line in list(f)]
        else:
            self._log.info(f'No byte data available')

        for i, stylesheet in enumerate(self._crawlData['css']):
            cssUrl = stylesheet['url']
            rules = stylesheet['rules']
            numRules = len(rules) if len(rules) > 0 else 1
            declarations = stylesheet['totalDeclarations'] if 'totalDeclarations' in stylesheet else 0
            references = stylesheet['totalReferences'] if 'totalReferences' in stylesheet else 0

            self._precursors['css'][i] = {}

            if self._isMissing(cssUrl): self._precursors['css'][i]['missing'] = True

            self._precursors['css'][i]['metrics'] = {
                'usedBytes': 0,
                'totalBytes': 0,
                'rules': numRules,
                'references': references
            }
            self._precursors['css'][i]['multipliers'] = {
                'heatmap': heatmapRatio
            }

            cssBytes = list(filter(lambda b: b['url'].endswith(cssUrl), cssByteMap))
            if len(cssBytes) > 0:
                cssBytes = cssBytes[0]
                self._precursors['css'][i]['metrics'].update({'usedBytes': cssBytes['usedBytes'], 'totalBytes': cssBytes['usedBytes']})


    def _calculateIFrameMetrics(self) -> tuple:
        self._log.info('Assessing IFrame element metrics')

        for i, el in enumerate(self._crawlData['iframe']):
            self._precursors['iframe'][i] = {}
            self._precursors['iframe'][i]['metrics'] = [{
                'width': 0,
                'height': 0,
                'x': 0,
                'y': 0,
                'styles': 0,
            }]
            self._precursors['iframe'][i]['multipliers'] = [{
                'location': 1.0,
                'semantic': 1.0
            }]
            # self._precursors['iframe'][i]['metrics'] = [{
            #     'width': el['width'],
            #     'height': el['height'],
            #     'x': el['left']+el['width'],
            #     'y': el['top']+el['height'],
            #     'styles': len(el['styles']) if 'styles' in el else 0,
            # }]
            # self._precursors['iframe'][i]['multipliers'] = [{
            #     'location': 1.0,
            #     'semantic': 1.0
            # }]


    def _calculateTextMetrics(self) -> None:
        '''
        - Plain text - num words * size
        - Link text - size * link value * (1|0)                (1|0 = link 200 vs 404)
        - Mixed

        unicode = 2 bytes per character
        '''
        self._log.info('Calculating text element metrics')

        for i, el in enumerate(self._crawlData['text']):
            numCharacters = len(el['text'])
            numWords = len(el['text'].split(' '))
            numLinks = 0

            self._precursors['text'][i] = {}
            self._precursors['text'][i]['metrics'] = [{
                'width': el['area']['width'],
                'height': el['area']['height'],
                'x': el['area']['left']+el['area']['width'],
                'y': el['area']['top']+el['area']['height'],
                'bytes': numCharacters * 2,
                'styles': len(el['classes']) if 'classes' in el else 0,
                'characters': numCharacters,
                'words': numWords,
                'links': numLinks
            }]
            self._precursors['text'][i]['multipliers'] = [{
                'location': 1.0,
                'semantic': 1.0
            }]
            # self._precursors['image'][i]['links'] = numLinks

            # Add annotation
            # x1 = int(el['left'])
            # y1 = int(el['top'])
            # x2 = int(el['left'])+int(el['width'])
            # y2 = int(el['top'])+int(el['height'])
            # self._addAnnotation('text', i, {
            #     'type': 'text',
            #     'xy': (x1, y1, x2, y2),
            #     'outline': (0, 204, 102)
            # })


    def _calculateImageMetrics(self) -> None:
        self._log.info('Calculating image element metrics')

        # Pass 1 - check if missing and determine average size of present images
        avgImgSize = {}
        for i, el in enumerate(self._crawlData['image']):
            self._precursors['image'][i] = {}

            if self._isMissing(el['url']): self._precursors['image'][i]['missing'] = True

            self._precursors['image'][i]['metrics'] = [{
                'width': r['width'],
                'height': r['height'],
                'bytes': 0,
                'styles': len(el['classes']) if 'styles' in el else 0,
            } for r in el['area']]
            self._precursors['image'][i]['multipliers'] = [{
                'location': 1.0,
                'semantic': 1.0
            }] * len(el['area'])

            if 'missing' not in self._precursors['image'][i]:
                parentString = '.'.join(el['parents'])
                if parentString not in avgImgSize: avgImgSize[parentString] = []
                for area in el['area']:
                    avgImgSize[parentString].append((area['width'], area['height']))

        if len(avgImgSize) > 0:
            for key in avgImgSize:
                avgImgSize[key] = (sum([r[0] for r in avgImgSize[key]]) / len(avgImgSize[key]),
                                   sum([r[1] for r in avgImgSize[key]]) / len(avgImgSize[key]))
            # avgImgSizeTotal = (sum([s[0] for s in avgImgSize.values()]) / len(avgImgSize),
            #                    sum([s[0] for s in avgImgSize.values()]) / len(avgImgSize))

        # Pass 2 - Adjust image sizes for missing images
        for i, el in enumerate(self._crawlData['image']):
            if 'missing' in self._precursors['image'][i]:
                wGuess, hGuess = self._guessImageSize(el, avgImgSize)

                for ii, r in enumerate(el['area']):
                    width, height = r['width'], r['height']

                    if 'width' in el and 'height' in el and (r['width'] < el['width'] and r['height'] < el['height']):
                        # use explicit size set from DOM
                        width, height = el['width'], el['height']
                    else:
                        if r['width'] < wGuess and r['height'] < hGuess:
                            width, height = wGuess, hGuess

                    self._precursors['image'][i]['metrics'][ii].update({'width': width, 'height': height})
                    self._precursors['image'][i]['metrics'][ii].update({'x': r['left'] + int(width/2), 'y': r['top'] + int(height/2)})
                    self._precursors['image'][i]['metrics'][ii].update({'width_augment': width - r['width'], 'height_augment': height - r['height']})

                    bbox = {
                        'left': int(r['left']),
                        'top': int(r['top']),
                        'right': int(r['left'])+int(r['width']),
                        'bottom': int(r['top'])+int(r['height'])
                    }
                    self._addAnnotation('image', i, el['url'], bbox, ii)


    def _guessImageSize(self, el, contextSizes=None):
        # Evaluate class names
        if 'classes' in el:
            for _class in el['classes']:
                if 'emoji' in _class:
                    return (S_EMOJI[0], S_EMOJI[1])
                elif 'avatar' in _class:
                    return (S_AVATAR[0], S_AVATAR[1])
                elif 'thumb' in _class or 'thumbnail' in _class or 'logo' in _class:
                    return (S_THUMBNAIL[0], S_THUMBNAIL[1])

        # Evaluate alt text
        if 'alt' in el:
            if ' ' not in el['alt']: # Character, single word, or URL
                if ((el['alt'][0] == ':' and el['alt'][-1] == ':')  or el['alt'] in EMOJI_NAMES):
                    return (S_EMOJI[0], S_EMOJI[1])

                if el['alt'].startswith('@') or 'avatar' in el['alt']:
                    return (S_AVATAR[0], S_AVATAR[1])

                if el['alt'].startswith('http'):
                    return (S_IMAGE_SM[0], S_IMAGE_SM[1])

            else: # descriptive alt text
                altWords = el['alt'].split(' ')
                # avgWordLength = sum(len(word) for word in altWords) / len(altWords)
                if len(altWords) > 5:
                    return (S_IMAGE_LG[0], S_IMAGE_LG[1])
                else:
                    return (S_IMAGE_SM[0], S_IMAGE_SM[1])

        parentString = '.'.join(el['parents'])
        if contextSizes and parentString in contextSizes:
            return contextSizes[parentString]
        else:
            return (S_THUMBNAIL[0], S_THUMBNAIL[1])


    def _calculateMediaMetrics(self) -> None:
        self._log.info('Calculating media element metrics')

        for i, el in enumerate(self._crawlData['media']):
            self._precursors['media'][i] = {}

            if self._isMissing(el['url']) or 'error' in el: self._precursors['media'][i]['missing'] = True

            self._precursors['media'][i]['metrics'] = [{
                'width': r['width'],
                'height': r['height'],
                'bytes': 0,
                'styles': len(el['classes']) if 'classes' in el else 0,
                'duration': 0
            } for r in el['area']]

            self._precursors['media'][i]['multipliers'] = [{
                'location': 1.0,
                'semantic': 1.0
            }] * len(el['area'])

            if 'missing' in self._precursors['media'][i]:
                for ii, r in enumerate(el['area']):
                    if r['width'] < S_VIDEO_SM[0] and r['height'] < S_VIDEO_SM[1]:
                        self._precursors['media'][i]['metrics'][ii].update({'width': S_VIDEO_SM[0], 'height': S_VIDEO_SM[1]})
                        self._precursors['media'][i]['metrics'][ii].update({'x': r['left'] + int(S_VIDEO_SM[0]/2), 'y': r['top'] + int(S_VIDEO_SM[1]/2)})
                        self._precursors['media'][i]['metrics'][ii].update({'width_augment': S_VIDEO_SM[0] - r['width'], 'height_augment': S_VIDEO_SM[1] - r['height']})

                    bbox = {
                        'left': int(r['left']),
                        'top': int(r['top']),
                        'right': int(r['left'])+int(r['width']),
                        'bottom': int(r['top'])+int(r['height'])
                    }
                    self._addAnnotation('media', i, el['url'], bbox, ii)


    def _calculateGitRepoMetrics(self) -> None:
        return


    def _calculateLocationMultipliers(self) -> None:
        pageCenterX = self._pageData['page']['width']
        pageCenterY = self._pageData['page']['height']

        p5 = int(len(self._pageData['page']['heatmap_x']) / 5)
        total = np.sum(self._pageData['page']['heatmap_x'])
        total = total if total > 0 else 1
        lDist = np.sum(self._pageData['page']['heatmap_x'][0:p5]) / total
        cDist = np.sum(self._pageData['page']['heatmap_x'][p5:p5*4]) / total
        rDist = np.sum(self._pageData['page']['heatmap_x'][p5*4:]) / total
        # print(f"{p5} {total} {lDist} {cDist} {rDist}")

        if self._template and 'zones' in self._template:
            for k in ['iframe', 'text', 'image', 'media']:
                for i, el in enumerate(self._precursors[k]):
                    for z in self._template['zones']:
                        if k == 'image' or k == 'media':
                            for ii, bbox in enumerate(el['area']):
                                if z['b'] > 0 and bbox['y'] > z['t'] and bbox['y'] < z['b'] and bbox['x'] > z['l'] and bbox['x'] < z['r']:
                                    self._precursors[k][i]['multipliers'][ii]['location'] += (z['multiplier'] - 1)
                                elif bbox['y'] > z['t'] and bbox['x'] > z['l'] and bbox['x'] < z['r']:
                                    self._precursors[k][i]['multipliers'][ii]['location'] += (z['multiplier'] - 1)
                                if self._precursors[k][i]['multipliers'][ii]['location'] < 0:
                                    self._precursors[k][i]['multipliers'][ii]['location'] = 0.0
                        else:
                            if z['b'] > 0 and bbox['y'] > z['t'] and bbox['y'] < z['b'] and bbox['x'] > z['l'] and bbox['x'] < z['r']:
                                self._precursors[k][i]['multipliers']['location'] += (z['multiplier'] - 1)
                            elif bbox['y'] > z['t'] and bbox['x'] > z['l'] and bbox['x'] < z['r']:
                                self._precursors[k][i]['multipliers']['location'] += (z['multiplier'] - 1)
                            if self._precursors[k][i]['multipliers']['location'] < 0: self._precursors[k][i]['multipliers']['location'] = 0.0


    def _calculateSemanticMultipliers(self):
        return


    def _calculatePageDamageScore(self): # @audit @todo
        self._log.info('Assessing page damage')
        '''
        # Calculate how much of the content area is utilized
        # utilizedArea = 0.0
        # extraPageHeight = 0
        # categoryArea = {'iframe': 0.0, 'image': 0.0, 'media': 0.0, 'text': 0.0}

        # for c in ['iframe', 'image', 'media', 'text']:
        #     for i, dataItem in enumerate(self._crawlData[c]):
        #         height, width, area = 0.0, 0.0, 0.0
        #         if c in ['image', 'media']:
        #             for rect in dataItem['area']:
        #                 if 'augmented_width' in dataItem or 'augmented_height' in dataItem:
        #                     extraPageHeight += dataItem['augmented_height'] - rect['height']
        #                     height += rect['height']
        #                     width += rect['width']
        #                 else:
        #                     area += rect['width'] * rect['height']
        #                     height += rect['height']
        #                     width += rect['width']
        #         else:
        #             if 'augmented_width' in dataItem or 'augmented_height' in dataItem:
        #                 area = dataItem['augmented_width'] * dataItem['augmented_height']

        #             if c == 'text':
        #                 area = dataItem['width'] * dataItem['height']
        #             elif c in ['image', 'media']:
        #                 extraPageHeight += dataItem['augmented_height'] - dataItem['height']
        #                 height += dataItem['augmented_height'] - dataItem['height']
        #                 width = dataItem['width']

        #         categoryArea[c] += area
        #         utilizedArea += area

        # print(f"{self._pageData['content']['height']} + {extraPageHeight}")
        # contentArea = self._pageData['content']['width'] * (self._pageData['content']['height'] + extraPageHeight)
        # self._pageData['content']['percentage'] = utilizedArea / contentArea
        # print(f'Utilized Area: {utilizedArea} / {contentArea} ({self._pageData["content"]["percentage"]:.2f}%)')

        # for dataKey in ['iframe', 'image', 'media', 'text']:
        #     c = categoryArea[dataKey] / utilizedArea
        #     self._pageData['content'][dataKey] = c
        #     print(f'{dataKey} coverage: {c:.2f}')
        '''

        groupDamage = {'css': 0.0, 'js': 0.0, 'iframe': 0.0, 'text': 0.0, 'image': 0.0, 'media': 0.0}
        actualDamage, potentialDamage = 0.0, 0.0

        # CSS damage calculation
        for i, precursor in self._precursors['css'].items():
            metrics = precursor['metrics']
            # damage = precursor['usedBytes'] \
            #     + (metrics['usedBytes'] * (metrics['references'] / metrics['numRules']))
            # for multiplier in precursor['multipliers'].values(): damage *= multiplier
            # base = cssBytes['usedBytes'] + (cssBytes['usedBytes'] * (references / numRules)) + (cssBytes['usedBytes'] * heatmapRatio)
            # print(f'{cssUrl} | Rules: {references} / {numRules} = {refRatio:.3f} | Bytes: {cssBytes["usedBytes"]} / {cssBytes["totalBytes"]} = {byteRatio:.3f} | {cssDmg:.3f}')
            damage = metrics['usedBytes'] \
                + (metrics['usedBytes'] * (metrics['references'] / metrics['rules'])) \
                + (metrics['usedBytes'] * precursor['multipliers']['heatmap'])

            self._precursors['css'][i]['value'] = damage
            potentialDamage += damage

            if 'missing' in self._precursors['css'][i]:
                groupDamage['css'] += damage
                actualDamage += damage

        # JavaScript damage calculation
        for i, precursor in self._precursors['js'].items():
            metrics = precursor['metrics']
            damage = 0.0

            self._precursors['js'][i]['value'] = damage
            potentialDamage += damage

            if 'missing' in self._precursors['js'][i]:
                groupDamage['js'] += damage
                actualDamage += damage


        for group in ['iframe', 'text', 'image', 'media']:
            for i, precursor in self._precursors[group].items():
                elDamage = 0.0
                for ii, el in enumerate(precursor['metrics']):
                    area = el['width'] * el['height']
                    for m in precursor['multipliers'][ii].values(): area *= m
                    elDamage += area

                potentialDamage += elDamage
                self._precursors[group][i]['value'] = elDamage
                if 'missing' in self._precursors[group][i]:
                    if group == 'text': print('text is missing')
                    groupDamage[group] += elDamage
                    actualDamage += elDamage


        with open(Path(self.cacheDir, 'data', 'precursors.jsonl'), 'w') as precursorFile:
            precursorJson = []
            for k in ['css', 'js', 'iframe', 'text', 'image', 'media']:
                for i in range(len(self._precursors[k])):
                    self._precursors[k][i]['type'] = k
                    self._precursors[k][i]['value'] = (self._precursors[k][i]['value'] / potentialDamage) if potentialDamage > 0.0 else 0.0
                    x = json.dumps(self._precursors[k][i])
                    precursorJson.append(x)
            precursorFile.write('\n'.join(precursorJson))

        pageDamage = (actualDamage / potentialDamage) if potentialDamage > 0.0 else 0.0
        pageDamagePercent = pageDamage * 100

        result = {}
        result['uri'] = self.uri
        result['is_archive'] = True if self.warcFile else False
        # result['urir_redirects'] = urirRedirects

        result['total_damage'] = pageDamagePercent
        result['potential_damage'] = {
            'total': potentialDamage,
            'css': sum(p['value'] for p in self._precursors['css'].values()),
            'js': sum(p['value'] for p in self._precursors['js'].values()),
            'iframe': sum(p['value'] for p in self._precursors['iframe'].values()),
            'text': sum(p['value'] for p in self._precursors['text'].values()),
            'image': sum(p['value'] for p in self._precursors['image'].values()),
            'multimedia': sum(p['value'] for p in self._precursors['media'].values()),
        }
        result['actual_damage'] = {
            'total': actualDamage,
            'css': sum(p['value'] for p in self._precursors['css'].values() if 'missing' in p),
            'js': sum(p['value'] for p in self._precursors['js'].values() if 'missing' in p),
            'iframe': sum(p['value'] for p in self._precursors['iframe'].values() if 'missing' in p),
            'text': sum(p['value'] for p in self._precursors['text'].values() if 'missing' in p),
            'image': sum(p['value'] for p in self._precursors['image'].values() if 'missing' in p),
            'multimedia': sum(p['value'] for p in self._precursors['media'].values() if 'missing' in p),
        }
        self.result = result

        with open(Path(self.cacheDir, 'result.json'), 'w') as f:
            f.write(json.dumps(result))

        self._log.info(f'CSS    : {result["actual_damage"]["css"]:0.3f}')
        self._log.info(f'JS     : {result["actual_damage"]["js"]:0.3f}')
        self._log.info(f'IFrame : {result["actual_damage"]["iframe"]:0.3f}')
        self._log.info(f'Text   : {result["actual_damage"]["text"]:0.3f}')
        self._log.info(f'Image  : {result["actual_damage"]["image"]:0.3f}')
        self._log.info(f'Media  : {result["actual_damage"]["multimedia"]:0.3f}')
        self._log.info(f'Total page damage: {self.result["total_damage"]}')


    def _addAnnotation(self, group, i, imgUrl, bbox, r=0) -> None:
        if group not in self._annotations: self._annotations[group] = {}
        if i not in self._annotations[group]: self._annotations[group][i] = {}
        if 'bbox' not in self._annotations[group][i]: self._annotations[group][i]['bbox'] = []
        self._annotations[group][i]['imgUrl'] = imgUrl
        self._annotations[group][i]['bbox'].append(bbox)


    def _setElementBoundaries(self):
        # Set css class or custom data attribute for tables, lists, container boundaries, etc
        return


    def _deriveElementContext(self):
        return


    def _downloadTimemaps(self) -> None:
        if Path(self.cacheDir, 'page', 'timemap.cdxj').is_file(): return

        uriR = self.uri[self.uri.rfind('http'):]
        memgatorURI = f'{MEMGATOR_HOST}/timemap/cdxj/{uriR}'
        self._log.info(f'Grabbing CDX timemap: {memgatorURI}')

        http = urllib3.PoolManager()
        res = http.request('GET', memgatorURI)
        if res.status == 200:
            try:
                resBody = res.data.decode("utf-8")
                with open(Path(self.cacheDir, 'page', 'timemap.cdxj'), 'w') as f:
                    f.write(resBody)
            except:
                self._log.error('Unable to save timemap data')
        else:
            self._log.error('Unable to retrieve timemap')


    def _clearError(self) -> None:
        Path.unlink(Path(self.cacheDir, 'error.json'), missing_ok=True)
        self.error = None


    def _setError(self, errorMessage) -> None:
        self.error = errorMessage
        with open(Path(self.cacheDir, 'error.json'), 'w') as f:
            json.dump({'error': errorMessage}, f, indent=2)