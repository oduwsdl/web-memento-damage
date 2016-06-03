#!/usr/bin/env python3

from ext.blueprint import RequestHandler, Blueprint


class Dashboard(Blueprint):
    def __init__(self, *args, **settings):
        Blueprint.__init__(self, name='dashboard', url_prefix='/dashboard',
                           *args, **settings)

    # Handlers
    class Index(RequestHandler):
        name = 'index'
        route = '/'

        def get(self, *args, **kwargs):
            self.render(".index.html")
