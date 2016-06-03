#!/usr/bin/env python3

from ext.blueprint import RequestHandler, Blueprint


class Settings(Blueprint):
    def __init__(self, *args, **settings):
        Blueprint.__init__(self, name='settings', url_prefix='/settings',
                           *args, **settings)

    # Handlers
    class Index(RequestHandler):
        name = 'index'
        route = '/'

        def get(self, *args, **kwargs):
            self.render(".index.html")

    class Account(RequestHandler):
        name = 'account'
        route = '/account'

        def get(self, *args, **kwargs):
            self.render(".account.html")
