import io
import json
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime
from urllib import parse
from pathlib import Path

from PIL import Image
from flask import Blueprint, request, render_template, Response, current_app as app

from memento_damage import utils
from memento_damage.analysis import DamageAnalysis


class API(Blueprint):
    def __init__(self):
        Blueprint.__init__(self, 'api', __name__, url_prefix='/api',
                           template_folder='views',
                           static_folder='static',
                           static_url_path='/static/home')


        @self.route('/', methods=['GET'])
        def api_index():
            try:
                parsed_uri = parse.urlparse(request.referrer)
                domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
            except:
                domain = app.config['BASE_URL'] + '/'

            return render_template("api_index.html", domain=domain)


        @self.route('/damage/status/<path:uri>', methods=['GET'])
        def api_status(uri):
            start = request.args.get('start', '0')
            start = int(start)
            uriFolder = utils.uriToFoldername(uri)

            analysisLines = []
            analysisLog = Path(app.config['CACHE_DIR'], uriFolder, 'analysis.log')
            if Path(analysisLog).exists():
                with open(analysisLog, 'r') as lf:
                    analysisLines = lf.read().splitlines()

            print(analysisLines)

            return Response(response=json.dumps(analysisLines), status=200, mimetype='application/json')


        @self.route('/damage/error/<path:uri>', methods=['GET'])
        def api_error(uri):
            uriFolder = utils.uriToFoldername(uri)
            print(f'Checking error for {uri}')

            errorFile = Path(app.config['CACHE_DIR'], uriFolder, 'error.json')
            if Path(errorFile).exists():
                try:
                    print('Attempting to open error file')
                    with open(errorFile, 'r') as ef:
                        ej = json.load(ef)
                        return Response(response=json.dumps(ej), status=200, mimetype='application/json')
                except Exception as e:
                    print(e.message)
                    return Response(response=json.dumps({'error': e.message}), status=200, mimetype='application/json')

            return Response(response=json.dumps({'error': False}), status=200, mimetype='application/json')


        @self.route('/damage/screenshot/<path:uri>', methods=['GET'])
        def api_screenshot(uri):
            uriFolder = utils.uriToFoldername(uri)
            screenshot_file = Path(app.config['CACHE_DIR'], uriFolder, 'screenshots', 'screenshot.png')

            if screenshot_file.exists():
                f = Image.open(screenshot_file)
                o = io.BytesIO()
                f.save(o, format="PNG")
                s = o.getvalue()
                return Response(response=s, status=200, mimetype='image/png')
            else:
                f = Image.open(Path('src', 'web', 'static', 'images', 'placeholder.jpg'))
                o = io.BytesIO()
                f.save(o, format="JPEG")
                s = o.getvalue()
                return Response(response=s, status=200, mimetype='image/jpg')


        @self.route('/damage/thumbnail/<path:uri>', methods=['GET'])
        def api_thumbnail(uri):
            uriFolder = utils.uriToFoldername(uri)
            thumbnail_file = Path(app.config['CACHE_DIR'], uriFolder, 'screenshots', 'thumbnail.jpg')

            if thumbnail_file.exists():
                f = Image.open(thumbnail_file)
                o = io.BytesIO()
                f.save(o, format="JPEG")
                s = o.getvalue()
                return Response(response=s, status=200, mimetype='image/jpeg')
            else:
                f = Image.open(Path('src', 'web', 'static', 'images', 'placeholder.jpg'))
                o = io.BytesIO()
                f.save(o, format="JPEG")
                s = o.getvalue()
                return Response(response=s, status=200, mimetype='image/jpg')


        # @self.route('/damage/data/image/<path:uri>', methods=['GET'])
        # def api_data_image(uri):
        #     uriFolder = utils.uriToFoldername(uri)
        #     dataFile = Path(app.config['CACHE_DIR'], uriFolder, 'data', 'image.jsonl')

        #     if dataFile.exists():
        #         return Response(response=s, status=200, mimetype='application/json')


        # @self.route('/damage/data/stylesheet/<path:uri>', methods=['GET'])
        # def api_data_stylesheet(uri):
        #     uriFolder = utils.uriToFoldername(uri)
        #     dataFile = Path(app.config['CACHE_DIR'], uriFolder, 'data', 'css.jsonl')

        #     if dataFile.exists():
        #         with open(dataFile, 'r') as f:
        #             j = f.read().splitlines()
        #         return Response(response=s, status=200, mimetype='application/json')


        # @self.route('/damage/data/javascript/<path:uri>', methods=['GET'])
        # def api_data_javascript(uri):
        #     uriFolder = utils.uriToFoldername(uri)
        #     dataFile = Path(app.config['CACHE_DIR'], uriFolder, 'data', 'javascript.jsonl')

        #     if dataFile.exists():
        #         return Response(response=s, status=200, mimetype='application/json')


        # @self.route('/damage/data/multimedia/<path:uri>', methods=['GET'])
        # def api_data_multimedia(uri):
        #     uriFolder = utils.uriToFoldername(uri)
        #     dataFile = Path(app.config['CACHE_DIR'], uriFolder, 'data', 'media.jsonl')

        #     if dataFile.exists():
        #         return Response(response=s, status=200, mimetype='application/json')


        # @self.route('/damage/data/text/<path:uri>', methods=['GET'])
        # def api_data_text(uri):
        #     uriFolder = utils.uriToFoldername(uri)
        #     dataFile = Path(app.config['CACHE_DIR'], uriFolder, 'data', 'text.jsonl')

        #     if dataFile.exists():
        #         return Response(response=s, status=200, mimetype='application/json')


        # @self.route('/damage/data/iframe/<path:uri>', methods=['GET'])
        # def api_data_iframe(uri):
        #     uriFolder = utils.uriToFoldername(uri)
        #     dataFile = Path(app.config['CACHE_DIR'], uriFolder, 'data', 'iframe.jsonl')

        #     if dataFile.exists():
        #         return Response(response=s, status=200, mimetype='application/json')


        @self.route('/damage/<path:uri>', methods=['GET'])
        def api_damage(uri):
            fresh = request.args.get('fresh', 'false')
            fresh = True if fresh.lower() == 'true' else False

            dereferencedUri = None
            uriFolder = utils.uriToFoldername(uri)
            uriCache = Path(app.config['CACHE_DIR'], uriFolder)

            if not Path(uriCache).is_dir():
                print(f"Cache directory does not exist for {uri}")
                utils.mkDir(uriCache)
                with open(Path(uriCache, 'uri.json'), 'w') as f:
                    json.dump({'original': uri}, f, indent=2)

            if Path(uriCache, 'uri.json').is_file():
                with open(Path(uriCache, 'uri.json'), 'r') as f:
                    j = json.load(f)
                    if 'dereference' in j:
                        dereferencedUri = j['dereference']
                        print(f'URI dereference loaded from cache: {dereferencedUri}')

            if dereferencedUri is None:
                dereferencedUri, status, error = dereferenceURI(uri)
                if status == 200:
                    dereferencedUri = utils.rectifyURI(dereferencedUri)
                    print(f'URI dereferenced: {dereferencedUri}')
                    with open(Path(uriCache, 'uri.json'), 'w') as f:
                        json.dump({'original': uri, 'dereference': dereferencedUri}, f, indent=2)
                else:
                    print(f'Error dereferencing URI: {uri}')
                    with open(Path(uriCache, 'error.json'), 'w') as f:
                        json.dump({'error': error}, f, indent=2)

                    return Response(response=json.dumps({'error': error}), status=200, mimetype='application/json')

            if fresh:
                result, processTime = self.analyzeUri(dereferencedUri, uriCache)
                result['calculation_time'] = processTime
                return Response(response=json.dumps({'error': error}), status=200, mimetype='application/json')
            else:
                if Path(uriCache, 'result.json').is_file():
                    with open(Path(uriCache, 'result.json'), 'r') as f:
                        result = json.load(f)
                        result['calculation_time'] = 0
                        return Response(response=json.dumps(result), status=200, mimetype='application/json')
                else:
                    result, processTime = self.analyzeUri(dereferencedUri, uriCache)
                    result['calculation_time'] = processTime
                    return Response(response=json.dumps(result), status=200, mimetype='application/json')


    def analyzeUri(self, uri, uriCache):
        analysis = DamageAnalysis(uriCache, uri, options=(
            False,
            True,
            20,
            60,
            (1920, 1080)
        ))

        startTime = datetime.now()

        analysis.crawl(recrawl=True)
        if analysis.error:
            endTime = datetime.now()
            processingTime = (endTime - startTime).total_seconds()
            return {'error': analysis.error}, processingTime

        analysis.analyze()
        endTime = datetime.now()
        processingTime = (endTime - startTime).total_seconds()
        if analysis.error:
            return {'error': analysis.error}

        return analysis.result, processingTime


def dereferenceURI(uri, timeout=30):
    print(f'Dereferencing URI: {uri}')
    try:
        response = requests.head(uri, allow_redirects=True, timeout=timeout, verify=False, headers={
            'User-Agent': 'URI dereferencer for ODU MementoDamage (memento-damage.cs.odu.edu) - ODU WS-DL (@WebSciDL), David Calano <dcalano@odu.edu>',
        })

        if response.status_code == 404:
            return None, response.status_code, '404: Page not found'
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
