import os
from tornado.web import StaticFileHandler

host                    = 'localhost'
port                    = 8880

debug                   = False

base_url                = 'http://{}:{}'.format(host, port)
base_dir                = os.path.abspath(os.path.dirname(__file__))
cache_dir               = os.path.join(base_dir, 'cache')

# Application settings
template_path           = os.path.join(base_dir, 'app', 'templates')
static_path             = os.path.join(base_dir, 'app', 'static')
static_handler_class    = StaticFileHandler

# Database settings (default to sqlite)
database_uri            = 'sqlite:///' + os.path.join(base_dir, 'app.db')



'''
# Listen address
HOST = 'localhost'
PORT = 8080

BASE_URL = 'http://{}:{}'.format(HOST, PORT)

# Statement for enabling the development environment
DEBUG = True

# Define the application directory
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Define template directory
TEMPLATE_DIR = os.path.join(BASE_DIR, 'app', 'templates')

# Define cache directory
CACHE_DIR = os.path.join(BASE_DIR, 'cache')

# Define the database - we are working with
# SQLite for this example
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
SQLALCHEMY_TRACK_MODIFICATIONS = True
DATABASE_CONNECT_OPTIONS = {}

# Application threads. A common general assumption is
# using 2 per available processor cores - to handle
# incoming requests using one and performing background
# operations using the other.
THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)*
CSRF_ENABLED     = True

# Use a secure, unique and absolutely secret key for
# signing the data. 
CSRF_SESSION_KEY = "secret"

# Secret key for signing cookies
SECRET_KEY = "secret"
'''
