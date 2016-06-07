from app import application
from gevent import wsgi
from tornado import httpserver, ioloop
from tornado.wsgi import WSGIAdapter


def start_server():
    server = httpserver.HTTPServer(application)
    # server.listen(application.settings.get('port'),
    #                    address='0.0.0.0')
    server.bind(application.settings.get('port'),
                       address='0.0.0.0')
    server.start(4) # Specify number of subprocesses
    
    print('Server is started at {}:{}'.format(
        'localhost', application.settings.get('port')))
    
    ioloop.IOLoop.current().start()


def start_gevent():
    server = wsgi.WSGIServer(('0.0.0.0', application.settings.get('port')),
                             WSGIAdapter(application))
    server.serve_forever()
    ioloop.IOLoop.current().start()


if __name__ == '__main__':
    start_server()