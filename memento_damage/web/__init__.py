import errno
import os
import pkgutil
import sys
import tempfile
import time
from optparse import OptionParser

from flask import Flask, Blueprint, render_template
from flask.globals import _request_ctx_stack
from flask.templating import DispatchingJinjaLoader
from flask_sqlalchemy import SQLAlchemy

from memento_damage import rmdir_recursive


class ModifiedLoader(DispatchingJinjaLoader):
    def _iter_loaders(self, template):
        bp = _request_ctx_stack.top.request.blueprint
        if bp is not None and bp in self.app.blueprints:
            loader = self.app.blueprints[bp].jinja_loader
            if loader is not None:
                yield self.app.blueprints[bp], loader

        loader = self.app.jinja_loader
        if loader is not None:
            yield self.app, loader


flask_app = None

class FlaskApp(Flask):
    def __init__(self, options):
        Flask.__init__(self, __name__)

        global flask_app
        flask_app = self

        # Make cache dir
        try:
            os.makedirs(options['CACHE_DIR'])
        except OSError, e:
            if e.errno != errno.EEXIST: raise

        # Configurations
        self.config.from_mapping(options)
        self.jinja_options = Flask.jinja_options.copy()
        self.jinja_options['loader'] = ModifiedLoader(self)

        self.configure_database()
        self.load_modules()
        self.create_database()

    def configure_database(self):
        # Define the database object which is imported
        # by modules and controllers
        self.db = SQLAlchemy(self)

    def load_modules(self):
        # Sample HTTP error handling
        @self.errorhandler(404)
        def not_found(error):
            return render_template('404.html'), 404

        # Load all modules
        modules_dir = os.path.join(self.config['BASE_DIR'], 'modules')
        sys.path.append(modules_dir)
        for importer, package_name, _ in pkgutil.iter_modules([modules_dir]):
            importer.find_module(package_name).load_module(package_name)

        # Register modules
        for mod_cls in Blueprint.__subclasses__():
            if str(mod_cls.__module__).startswith('mod'):
                mod = mod_cls()
                self.register_blueprint(mod)

    def create_database(self):
        # Build the database:
        # This will create the database file using SQLAlchemy
        self.db.create_all()

    def run_server(self):
        self.run(host=self.config['HOST'], port=self.config['PORT'], debug=self.config['DEBUG'],
                      threaded=True, use_reloader=False)

        # If CLEAN_CACHE set to True, clean cache directory after server is closed
        if self.config['CLEAN_CACHE']:
            time.sleep(3)
            rmdir_recursive(self.config['CACHE_DIR'], exception_files=[r'app.db'])

def main():
    parser = OptionParser()
    parser.add_option("-O", "--output-dir",
                      dest="CACHE_DIR", default=None,
                      help="output directory (optional)")
    parser.add_option("-H", "--host",
                      dest="HOST", default='0.0.0.0',
                      help="host of server")
    parser.add_option("-P", "--port",
                      dest="PORT", default=8080,
                      help="port of server")
    parser.add_option("-d", "--debug",
                      action="store_true", dest="DEBUG", default=False,
                      help="print server debug messages")

    (options, args) = parser.parse_args()
    options = vars(options)

    # If option -O is provided, use it
    if options['CACHE_DIR']:
        options['CLEAN_CACHE'] = False
        output_dir = options['CACHE_DIR']
        # Make output_dir absolute
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(os.getcwd(), output_dir)
            options['CACHE_DIR'] = os.path.abspath(output_dir)
    # Otherwise make temp dir
    else:
        options['CACHE_DIR'] = tempfile.mkdtemp()
        options['CLEAN_CACHE'] = True

    # Add some necessary config variables
    options['BASE_URL']                         = 'http://{}:{}'.format(options['HOST'], options['PORT'])
    options['BASE_DIR']                         = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    options['TEMPLATE_DIR']                     = os.path.join(options['BASE_DIR'], 'templates')
    options['SQLALCHEMY_DATABASE_URI']          = 'sqlite:///' + os.path.join(options['CACHE_DIR'], 'app.db')
    options['SQLALCHEMY_TRACK_MODIFICATIONS']   = False
    options['DATABASE_CONNECT_OPTIONS']         = {}
    options['THREADS_PER_PAGE']                 = 10
    options['CSRF_ENABLED']                     = True
    options['CSRF_SESSION_KEY']                 = 'secret'
    options['SECRET_KEY']                       = 'secret'

    FlaskApp(options).run_server()


if __name__ == "__main__":
    main()