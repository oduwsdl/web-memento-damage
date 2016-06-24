import json
from datetime import datetime

import errno

import os
from app import database
from app.models.models import MementoModel
from ext.blueprint import Blueprint, RequestHandler
from ext.tools import Command
from sqlalchemy import desc
from tornado import web
from hashlib import md5


class API(Blueprint):
    def __init__(self, *args, **settings):
        Blueprint.__init__(self, url_prefix='/api', *args, **settings)

        self.screenshot_dir = os.path.join(
            self.application.settings.get('cache_dir'), 'screenshot')
        self.log_dir = os.path.join(
            self.application.settings.get('cache_dir'), 'log')
        self.html_dir = os.path.join(
            self.application.settings.get('cache_dir'), 'html')

        try:
            os.makedirs(self.screenshot_dir)
            os.makedirs(self.log_dir)
            os.makedirs(self.html_dir)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise


    '''
    Handlers =================================================================
    '''
    class Index(RequestHandler):
        route = ['', '/']

        @web.asynchronous
        def get(self, *args, **kwargs):
            self.render('.index.html')

    class Damage(RequestHandler):
        route = ['/damage/([^/]+)', '/damage/([^/]+)/([^/]+)']

        @web.asynchronous
        def get(self, uri, fresh="false"):
            print uri, fresh

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

                    result = json.loads(result)
                    result['is_archive'] = True
                    result['archive_time'] = time.isoformat()

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

            # Define path for each arguments of crawl.js
            crawljs_script = os.path.join(
                self.application.settings.get('base_dir'),
                'ext', 'phantomjs', 'crawl.js'
            )
            # Define damage.py location
            damage_py_script = os.path.join(
                self.application.settings.get('base_dir'),
                'ext', 'damage.py'
            )

            # Define arguments
            screenshot_file = '{}.png'.format(os.path.join(
                self.blueprint.screenshot_dir, hashed_url))
            html_file = '{}.html'.format(os.path.join(
                self.blueprint.html_dir, hashed_url))
            log_file = '{}.log'.format(os.path.join(
                self.blueprint.log_dir, hashed_url))
            images_log_file = '{}.img.log'.format(os.path.join(
                self.blueprint.log_dir, hashed_url))
            csses_log_file = '{}.css.log'.format(os.path.join(
                self.blueprint.log_dir, hashed_url))
            crawler_log_file = '{}.crawl.log'.format(os.path.join(
                self.blueprint.log_dir, hashed_url))

            # Logger
            f = open(crawler_log_file, 'w')
            f.write('')
            f.close()

            f = open(crawler_log_file, 'a')

            def log_output(out, page=None):
                def write(line):
                    f.write(line + '\n')
                    print(line)

                    if 'background_color' in line and page:
                        page['background_color'] = json.loads(line)\
                                                   ['background_color']
                    if 'result' in line:
                        line = json.loads(line)

                        result = line['result']
                        result['is_success'] = True
                        result['is_archive'] = False

                        result = json.dumps(result)

                        # Write result to db
                        model.response_time = datetime.now()
                        model.result = result
                        database.session.add(model)
                        database.session.commit()

                        self.write(result)
                        self.finish()

                if out and hasattr(out, 'readline'):
                    for line in iter(out.readline, b''):
                    #for line in out.readlines():
                        line =  line.strip()
                        write(line)
                else:
                    write(out)

            # Error
            def result_error(err = 'Request time out'):
                if not self._finished:
                    result = {
                        'is_success' : False,
                        'error' : err
                    }

                    self.write(json.dumps(result))
                    self.finish()

            # page background-color will be set from phantomjs result
            page = {
                'background_color': 'FFFFFF'
            }

            # Crawl page with phantomjs crawl.js via arguments
            # Equivalent with console:
            #   phantomjs crawl.js <screenshot> <html> <log>
            cmd = Command(['phantomjs', crawljs_script, uri,screenshot_file,
                           html_file, log_file], log_output)
            err_code = cmd.run(10 * 60, args=(page, ))

            if err_code == 0:
                # Calculate damage with damage.py via arguments
                # Equivalent with console:
                #   python damage.py <img_log> <css_log> <screenshot_log> <bg>
                cmd = Command(['python', damage_py_script, images_log_file,
                               csses_log_file, screenshot_file,
                               page['background_color']],
                              log_output)
                err_code = cmd.run(10 * 60)
                if err_code != 0:
                    result_error()
            else:
                result_error()