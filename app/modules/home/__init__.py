import base64
import errno
import json
from hashlib import md5

from PyQt4.QtGui import QApplication

import os
from ext.blueprint import Blueprint, RequestHandler
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

    def crawl(self, url, writer, on_finished_fn):
        class CustomCrawlListener(CrawlListener):
            message = []
            def on_start(self, id, browser):
                writer.write('Browser {} is starting crawl {}\n\n'
                    .format(id, browser.page().mainFrame().requestedUrl()))
                writer.flush()

            def on_loaded(self, id, browser):
                url = str(browser.page().mainFrame().requestedUrl().toString())
                hashed_url = md5(url).hexdigest()

                browser.get_html('{}.html'.format(
                    os.path.join(writer.blueprint.html_dir, hashed_url)))
                browser.take_screenshot('{}.png'.format(
                    os.path.join(writer.blueprint.screenshot_dir, hashed_url)))
                browser.get_images('{}.img.log'.format(
                    os.path.join(writer.blueprint.log_dir, hashed_url)))
                browser.get_stylesheets('{}.css.log'.format(
                    os.path.join(writer.blueprint.log_dir, hashed_url)))
                browser.get_resources('{}.log'.format(
                    os.path.join(writer.blueprint.log_dir, hashed_url)))

                writer.write('Browser {} is finished crawl {}\n\n'
                             .format(id, url))
                writer.flush()

            def on_resource_received(self, log, id, *browser):
                writer.write('Browser {} receive resource {}\n\n'
                             .format(id, log['url']))
                writer.flush()

            def on_finished(self, sessions):
                urls = [len(urls) for id, urls, status in sessions]

                writer.write('All Finished\n\n')
                writer.write('{} URIs has crawled in {} sessions\n\n'
                             .format(sum(urls), len(urls)))
                writer.flush()
                on_finished_fn()

        app = QApplication([])
        crawler = Crawler(app, CustomCrawlListener())
        crawler.add_blacklist('http://web.archive.org/static')
        crawler.start(url)

        app.exec_()

    '''
    Handlers =================================================================
    '''
    class Index(RequestHandler):
        route = ['/', '/memento']

        @web.asynchronous
        def get(self, *args, **kwargs):
            self.render(".index.html")


    class CheckMementoSession(RequestHandler):
        route = ['/memento/check/session']

        @web.asynchronous
        def get(self, *args, **kwargs):
            base64url = self.get_query_argument('base64url')
            session_urls = json.loads(base64.b64decode(base64url))
            self.blueprint.crawl(session_urls, self, self._on_crawl_finished)

        def _on_crawl_finished(self):
            self.finish()


    class CheckMemento(RequestHandler):
        route = ['/memento/check']

        @web.asynchronous
        def get(self, *args, **kwargs):
            url = self.get_query_argument('url')
            type = self.get_query_argument('type')

            if type.upper() == 'URI-M':
                self.blueprint.crawl(url, self, self._on_crawl_finished)
            else:
                self.write('Crawl URI-R {}'.format(url))
                self.flush()

                m = MementoWeb(url)
                memento_urls = m.find()
                sessions_urls = [memento_urls[x:x+10]
                                   for x in xrange(0, len(memento_urls), 10)]

                # sessions_urls = sessions_urls[:50]

                self.running_sessions = len(sessions_urls)
                self.stopped_sessions = 0

                self.write('Crawl URI-M in {} sessions'.format(len(sessions_urls)))
                for session_urls in sessions_urls:
                    check_url = self.application.settings.get('base_url') + \
                                self.reverse_url('.CheckMementoSession') + \
                                '?base64url={}'.format(
                                    base64.b64encode(json.dumps(session_urls)))

                    self.write('Crawl URI-M Session {}'.format(check_url))
                    self.flush()

                    client = httpclient.AsyncHTTPClient()
                    client.fetch(check_url, callback=self._on_response)

        def _on_response(self, response):
            if response.error:
                self.write("Error: %s" % response.error)
            else:
                self.write(escape.xhtml_escape(response.body) + '<br/>')
            self.flush()

            self.stopped_sessions += 1
            if self.stopped_sessions >= self.running_sessions:
                self.finish()

        def _on_crawl_finished(self):
            self.finish()

