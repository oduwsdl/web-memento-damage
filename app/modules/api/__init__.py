from ext.blueprint import Blueprint, RequestHandler
from tornado import web


class API(Blueprint):
    def __init__(self, *args, **settings):
        Blueprint.__init__(self, url_prefix='/api', *args, **settings)


    '''
    Handlers =================================================================
    '''
    class Index(RequestHandler):
        route = ['', '/']

        @web.asynchronous
        def get(self, *args, **kwargs):
            self.render('.index.html')