import base64
import errno
import io
import json
from hashlib import md5

import thread
from PyQt4.QtGui import QApplication
from datetime import datetime

import os
from PIL import Image
from ext.blueprint import Blueprint, RequestHandler
from ext.damage import SiteDamage
from ext.memento import MementoWeb
from ext.crawl import CrawlListener, Crawler
from tornado import web, httpclient, escape


# from gevent import monkey, spawn, spawn_later;
# monkey.patch_all()


class Memento(Blueprint):
    def __init__(self, *args, **settings):
        Blueprint.__init__(self, url_prefix='', *args, **settings)

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
        route = ['/', '/memento']

        @web.asynchronous
        def get(self, *args, **kwargs):
            self.render(".index.html")


    class CheckMemento(RequestHandler):
        route = ['/memento/check']

        @web.asynchronous
        def get(self, *args, **kwargs):
            url = self.get_query_argument('url')
            type = self.get_query_argument('type')

            self.render(".check.html", url=url, type=type)

    class GetUriM(RequestHandler):
        route = ['/memento/mementos']

        @web.asynchronous
        def get(self, *args, **kwargs):
            url = self.get_query_argument('uri-r')
            m = MementoWeb(url)
            memento_urls = m.find()

            self.write(json.dumps(memento_urls))
            self.finish()

    class Screenshot(RequestHandler):
        route = ['/memento/screenshot']

        @web.asynchronous
        def get(self, *args, **kwargs):
            url = self.get_query_argument('url')
            if not url.endswith('/'):
                url += '/'

            hashed_url = md5(url).hexdigest()

            screenshot_file = '{}.png'.format(os.path.join(
                self.blueprint.screenshot_dir, hashed_url))
            f = Image.open(screenshot_file)
            o = io.BytesIO()
            f.save(o, format="JPEG")
            s = o.getvalue()

            self.set_header('Content-type', 'image/png')
            self.set_header('Content-length', len(s))
            self.write(s)
            self.finish()

    class CheckDamage(RequestHandler):
        route = ['/memento/damage']

        @web.asynchronous
        def get(self, *args, **kwargs):
            uri = self.get_query_argument('uri')
            writer = self

            class CustomCrawlListener(CrawlListener):
                def __init__(self):
                    self.result = {}

                def on_start(self, id, browser):
                    print('Browser {} is starting crawl {}\n\n'
                        .format(id, browser.page().mainFrame().requestedUrl()))
                    self.timestart = datetime.now()

                def on_loaded(self, id, browser):
                    url = str(browser.page().mainFrame().requestedUrl().toString())
                    hashed_url = md5(url).hexdigest()

                    browser.get_html('{}.html'.format(
                        os.path.join(writer.blueprint.html_dir, hashed_url)))
                    browser.take_screenshot('{}.png'.format(
                        os.path.join(writer.blueprint.screenshot_dir, hashed_url)))
                    images_log = browser.get_images('{}.img.log'.format(
                        os.path.join(writer.blueprint.log_dir, hashed_url)))
                    csses_log = browser.get_stylesheets('{}.css.log'.format(
                        os.path.join(writer.blueprint.log_dir, hashed_url)))
                    browser.get_resources('{}.log'.format(
                        os.path.join(writer.blueprint.log_dir, hashed_url)))

                    print('Browser {} is finished crawl {}\n\n'
                                 .format(id, url))
                    print('Calculating site damage...')

                    damage = SiteDamage(images_log, csses_log, '{}.png'.format(
                        os.path.join(writer.blueprint.screenshot_dir, hashed_url)),
                        browser.get_background_color())

                    potential_damage = damage.calculate_potential_damage()
                    print('Potential Damage : {}'.format(potential_damage))

                    actual_damage = damage.calculate_actual_damage()
                    print('Actual Damage : {}'.format(actual_damage))
                    print('Total Damage : {}'.format(
                        actual_damage/potential_damage if potential_damage
                        != 0 else 0))

                    self.result['images'] = images_log
                    self.result['csses'] = csses_log
                    self.result['potential_damage'] = potential_damage
                    self.result['actual_damage'] = actual_damage
                    self.result['total_damage'] = \
                        actual_damage/potential_damage \
                        if potential_damage != 0 else 0

                def on_resource_received(self, log, id, *browser):
                    print('Browser {} receive resource {}\n\n'
                                 .format(id, log['url']))

                def on_finished(self, sessions):
                    self.timefinish = datetime.now()
                    process_time = (self.timefinish -
                                    self.timestart).microseconds / 1000

                    urls = [len(urls) for id, urls, status in sessions]

                    print('All Finished\n\n')
                    print('{} URIs has crawled in {} sessions in {} '
                          'seconds\n\n'.format(sum(urls), len(urls),
                                                   process_time))

                    writer.write(json.dumps(self.result))
                    writer.finish()

            app = QApplication([])
            crawler = Crawler(app, CustomCrawlListener())
            crawler.add_blacklist('http://web.archive.org/static')
            crawler.start(uri)

            app.exec_()

            # self.write(json.dumps({'damage' : 0}))
            # self.finish()

