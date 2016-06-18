from app import application
from gevent import wsgi
from tornado import httpserver, ioloop
from tornado.wsgi import WSGIAdapter
import sys

port = sys.argv[1] if len(sys.argv) > 1 else application.settings.get('port')
host = sys.argv[2] if len(sys.argv) > 2 else application.settings.get(
    'host', '0.0.0.0')

def start_server():
    server = httpserver.HTTPServer(application)
    # server.listen(application.settings.get('port'),
    #                    address='0.0.0.0')
    server.bind(port, address=host)
    server.start(4) # Specify number of subprocesses

    print('Server is started at {}:{}'.format(
        host, port))

    ioloop.IOLoop.current().start()


def start_gevent():
    server = wsgi.WSGIServer((host, port),
                             WSGIAdapter(application))
    server.serve_forever()
    ioloop.IOLoop.current().start()


if __name__ == '__main__':
    start_server()
