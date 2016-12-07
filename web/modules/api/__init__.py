import io
import json
import os
from datetime import datetime
from hashlib import md5
from urlparse import urlparse

from PIL import Image
from sqlalchemy import desc
from tornado import web

from cli.damage import CrawlAndCalculateDamage
from ext.blueprint import Blueprint, RequestHandler
from web import database
from web.models.models import MementoModel


class API(Blueprint):
    def __init__(self, *args, **settings):
        Blueprint.__init__(self, url_prefix='/api', *args, **settings)
        self.cache_dir = self.application.settings.get('cache_dir')


    '''
    Handlers =================================================================
    '''
    class Index(RequestHandler):
        route = ['', '/']

        @web.asynchronous
        def get(self, *args, **kwargs):
            referer = self.request.headers.get("Referer")
            parsed_uri = urlparse(referer)
            domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)

            self.render('.index.html', domain=domain)

    class ProgressCheckDamage(RequestHandler):
        route = ['/damage/progress/([^/]+)',
                 '/damage/progress/([^/]+)/([^/]+)']

        @web.asynchronous
        def get(self, uri, start=0):
            start = int(start)
            hashed_uri = md5(uri).hexdigest()

            crawler_log_file = os.path.join(self.blueprint.cache_dir, hashed_uri, 'crawl.log')
            with open(crawler_log_file, 'rb') as f:
                for idx, line in enumerate(f.readlines()):
                    if idx >= start:
                        self.write(line)
                self.finish()

    class CheckError(RequestHandler):
        route = ['/damage/error/([^/]+)']

        @web.asynchronous
        def get(self, uri):
            hashed_uri = md5(uri).hexdigest()

            crawler_log_file = os.path.join(self.blueprint.cache_dir, hashed_uri, 'crawl.log')
            with open(crawler_log_file, 'rb') as f:
                for idx, line in enumerate(f.readlines()):
                    if 'crawl-result' in line:
                        json_line = json.loads(line)
                        self.write(json.dumps(json_line['crawl-result']))
                        self.finish()

                if not self._finished:
                    self.write(json.dumps({'error': False}))
                    self.finish()

    class Screenshot(RequestHandler):
        route = ['/damage/screenshot/([^/]+)']

        @web.asynchronous
        def get(self, uri):
            hashed_uri = md5(uri).hexdigest()

            screenshot_file = os.path.join(self.blueprint.cache_dir, hashed_uri, 'screenshot.png')
            f = Image.open(screenshot_file)
            o = io.BytesIO()
            f.save(o, format="JPEG")
            s = o.getvalue()

            self.set_header('Content-type', 'image/png')
            self.set_header('Content-length', len(s))
            self.write(s)
            self.finish()

    class Damage(RequestHandler):
        route = ['/damage/([^/]+)', '/damage/([^/]+)/([^/]+)']

        @web.asynchronous
        def get(self, uri, fresh="false"):
            self.start_time = datetime.now()

            # since all query string arguments are in unicode, cast fresh to
            # boolean
            if fresh.lower() == 'true': fresh = True
            elif fresh.lower() == 'false': fresh = False
            else: fresh = False

            hashed_url = md5(uri).hexdigest()

            # If fresh == True, do fresh calculation
            if fresh:
                self.do_fresh_calculation(uri, hashed_url)
            else:
                # If there are calculation history, use it
                last_calculation = self.check_calculation_archives(hashed_url)
                if last_calculation:
                    result = last_calculation.result
                    time = last_calculation.response_time

                    self.end_time = datetime.now()

                    result = json.loads(result)
                    result['is_archive'] = True
                    result['archive_time'] = time.isoformat()
                    result['calculation_time'] = (self.end_time - self.start_time).seconds

                    self.write(result)
                    self.finish()
                else:
                    self.do_fresh_calculation(uri, hashed_url)

        def check_calculation_archives(self, hashed_uri):
            last_calculation = database.session.query(MementoModel)\
                .filter(MementoModel.hashed_uri==hashed_uri)\
                .order_by(desc(MementoModel.response_time))\
                .first()

            return last_calculation

        def do_fresh_calculation(self, uri, hashed_url):
            # Instantiate MementoModel
            model = MementoModel()
            model.uri = uri
            model.hashed_uri = hashed_url
            model.request_time = datetime.now()


            tornado_request = self
            class ModifiedCrawlAndCalculateDamage(CrawlAndCalculateDamage):
                def write_output(self, logger_file, result_file, summary_file, line):
                    CrawlAndCalculateDamage.write_output(self, logger_file, result_file, summary_file, line)

                    if 'crawl-result' in line:
                        line = json.loads(line)
                        self._crawl_result = line['crawl-result']

                    if 'result' in line:
                        try:
                            tornado_request.end_time = datetime.now()
                            line = json.loads(line)

                            result = line['result']
                            result.update(self._crawl_result)
                            result['error'] = False
                            result['is_archive'] = False
                            result['message'] = 'Calculation is finished in {} seconds'.format(
                                (tornado_request.end_time - tornado_request.start_time).seconds
                            )
                            result['timer'] = {
                                'request_time': (tornado_request.start_time - datetime(1970,1,1)).total_seconds(),
                                'response_time': (tornado_request.end_time - datetime(1970,1,1)).total_seconds()
                            }
                            result['calculation_time'] = (tornado_request.end_time - tornado_request.start_time).seconds



                            result = line['result']
                            result['error'] = False
                            result['is_archive'] = False
                            result['calculation_time'] = (tornado_request.end_time - tornado_request.start_time) \
                                .seconds

                            result = json.dumps(result)

                            # Write result to db
                            model.response_time = datetime.now()
                            model.result = result
                            database.session.add(model)
                            database.session.commit()

                            tornado_request.write(result)
                            tornado_request.finish()
                        except (ValueError, KeyError) as e:
                            pass

                def result_error(self, err=''):
                    if not tornado_request._finished:
                        result = {
                            'error': True,
                            'message': err
                        }

                        tornado_request.write(json.dumps(result))
                        tornado_request.finish()


            ModifiedCrawlAndCalculateDamage(uri, self.blueprint.cache_dir, {'redirect': True})\
                .do_calculation()
