import os
import pkgutil
import sys
from optparse import OptionParser

from flask import Flask, Blueprint, render_template
from flask.globals import _request_ctx_stack
from flask.templating import DispatchingJinjaLoader
from flask_sqlalchemy import SQLAlchemy


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


def create_flask_app(options):
    # Define the WSGI application object
    flask_app = Flask(__name__)

    # Configurations
    flask_app.config.from_mapping(options)
    flask_app.jinja_options = Flask.jinja_options.copy()
    flask_app.jinja_options['loader'] = ModifiedLoader(flask_app)

    # Define the database object which is imported
    # by modules and controllers
    db = SQLAlchemy(flask_app)

    # Sample HTTP error handling
    @flask_app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    # Load all modules
    modules_dir = os.path.join(options['BASE_DIR'], 'modules')
    sys.path.append(modules_dir)
    for importer, package_name, _ in pkgutil.iter_modules([modules_dir]):
        importer.find_module(package_name).load_module(package_name)

    # Register modules
    for mod_cls in Blueprint.__subclasses__():
        if str(mod_cls.__module__).startswith('mod'):
            mod = mod_cls()
            flask_app.register_blueprint(mod)

    # Build the database:
    # This will create the database file using SQLAlchemy
    db.create_all()

    return flask_app


def main():
    parser = OptionParser()
    parser.add_option("-C", "--cache-dir",
                      dest="CACHE_DIR", default=os.getcwd(),
                      help="cache directory")
    parser.add_option("-H", "--host",
                      dest="HOST", default='0.0.0.0',
                      help="host of server")
    parser.add_option("-P", "--port",
                      dest="PORT", default=8080,
                      help="port of server")
    parser.add_option("-D", "--debug",
                      action="store_true", dest="DEBUG", default=False,
                      help="print server debug messages")

    (options, args) = parser.parse_args()
    options = vars(options)

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

    flask_app = create_flask_app(options)
    flask_app.run(host=options['HOST'], port=options['PORT'], debug=options['DEBUG'],
            threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()