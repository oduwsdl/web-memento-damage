import errno
import json
from urlparse import urlparse

import os
from ext.blueprint import Blueprint, RequestHandler
from ext.memento import MementoWeb
from tornado import web


class Memento(Blueprint):
    def __init__(self, *args, **settings):
        Blueprint.__init__(self, url_prefix='', *args, **settings)

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
            type = self.get_query_argument('type', 'URI-M')
            fresh = self.get_query_argument('fresh', 'false')

            if not urlparse(url).scheme:
                self.redirect('/memento/check?url=http://{}&type={}&fresh={}'.format(
                    url, type, fresh
                ))

            self.render(".check.html", url=url, type=type, fresh=fresh)

    class GetUriM(RequestHandler):
        route = ['/memento/mementos']

        @web.asynchronous
        def get(self, *args, **kwargs):
            url = self.get_query_argument('uri-r')
            m = MementoWeb(url)
            memento_urls = m.find()

            self.write(json.dumps(memento_urls))
            self.finish()

