import argparse, errno, os, pkgutil, sys, tempfile, threading, time
from pathlib import Path
import argparse, logging
import sys, time
from importlib.util import module_from_spec

from pathlib import Path
from flask import Flask, Blueprint, render_template, request
from flask.templating import DispatchingJinjaLoader
from flask_sqlalchemy import SQLAlchemy

from memento_damage import utils

flask_app = None

LOG_FILE = 'server.log'
LOG_FORMAT = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
LOG_LEVEL = 30
log = None


class ModifiedLoader(DispatchingJinjaLoader):
    def _iter_loaders(self, template):
        bp = request.blueprint
        if bp is not None and bp in self.app.blueprints:
            loader = self.app.blueprints[bp].jinja_loader
            if loader is not None:
                yield self.app.blueprints[bp], loader

        loader = self.app.jinja_loader
        if loader is not None:
            yield self.app, loader


class FlaskApp(Flask):
    def __init__(self, options):
        Flask.__init__(self, __name__)

        global flask_app
        flask_app = self

        try:
            utils.mkDir(options['CACHE_DIR'])
        except OSError as e:
            if e.errno != errno.EEXIST: raise

        # Configurations
        self.config.from_mapping(options)
        self.jinja_options = Flask.jinja_options.copy()
        self.jinja_options['loader'] = ModifiedLoader(self)

        self.db = SQLAlchemy(self)
        self.load_modules()

        with self.app_context():
            self.db.create_all()


    def load_modules(self):
        @self.errorhandler(404)
        def not_found(error):
            return render_template('404.html'), 404

        # Load all modules
        modules_dir = os.path.join(self.config['BASE_DIR'], 'modules')
        sys.path.append(modules_dir)
        for finder, package_name, _ in pkgutil.iter_modules([modules_dir]):
            spec = finder.find_spec(package_name)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)

        # Register modules
        for mod_cls in Blueprint.__subclasses__():
            if str(mod_cls.__module__).startswith('mod'):
                mod = mod_cls()
                self.register_blueprint(mod)


    def run_server(self):
        self.run(host=self.config['HOST'],
                 port=self.config['PORT'],
                 debug=self.config['DEBUG'],
                 threaded=True,
                 use_reloader=False)

        if self.config['CLEAN_CACHE']:
            time.sleep(3)
            utils.rmdir_recursive(self.config['CACHE_DIR'], exception_files=[r'server.db'])


def main():
    args = parseArgs()
    options = {
        'HOST': args.HOST,
        'PORT': args.PORT,
        'DEBUG': args.DEBUG,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'DATABASE_CONNECT_OPTIONS': {},
        'THREADS_PER_PAGE': 10,
        'CSRF_ENABLED': True,
        'CSRF_SESSION_KEY': 'secret',
        'SECRET_KEY': 'secret'
    }

    if args.CACHE:
        options['CLEAN_CACHE'] = False
        cacheDir = Path(args.CACHE)
        if cacheDir.is_dir():
            options['CACHE_DIR'] = cacheDir.absolute()
    else:
        options['CACHE_DIR'] = tempfile.mkdtemp()
        options['CLEAN_CACHE'] = True

    options['BASE_URL'] = f"http://{args.HOST}:{args.PORT}"
    options['BASE_DIR'] = Path(__file__).parents[0].absolute()
    options['TEMPLATE_DIR'] = Path(options['BASE_DIR'], 'templates')
    options['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{Path(options['CACHE_DIR'], 'server.db')}"

    '''
    Log initialization
    '''
    try:
        utils.mkDir(options['CACHE_DIR'])

        logMode = 'a'
        fileHandler = logging.FileHandler(Path(options['CACHE_DIR'], LOG_FILE), mode=logMode)
        fileHandler.setFormatter(LOG_FORMAT)
        log = logging.getLogger('server')
        log.addHandler(fileHandler)
        log.setLevel(LOG_LEVEL)
        log.info('Server initialized')
    except:
        print('FATAL: Unable to initialize server cache')
        exit(1)

    # print('Starting worker thread')
    # threading.Thread(target=monitorQueue).start()

    print('Starting Flask server')
    print(f" * Cache directory: {options['CACHE_DIR']}")
    FlaskApp(options).run_server()


def parseArgs():
    parser = argparse.ArgumentParser(
        prog='Memento Damage Web Server',
        description='Web server for Memento Damage utility',
        usage='%(prog)s [options] <URI>',
        epilog='oduwsdl.github.io (@WebSciDL)')

    parser.add_argument('-c', '--cache', dest='CACHE',
                        default=None,
                        help='Set specified cache path')
    parser.add_argument('-d', '--debug', dest='DEBUG',
                        action='store_true', default=False,
                        help='Enable debugging mode (default: off)')
    parser.add_argument("-H", "--host",
                        dest="HOST", default='0.0.0.0',
                        help="Custom host address (default 0.0.0.0)")
    parser.add_argument("-P", "--port",
                        dest="PORT", default=8080,
                        help="Custom port (default: 8080)")

    args = parser.parse_args()

    if len(sys.argv) < 1:
        parser.print_help()
        exit(1)

    return args


if __name__ == "__main__":
    main()
