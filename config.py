import os
from tornado.web import StaticFileHandler

host                    = 'localhost'
port                    = 8880

debug                   = False

base_url                = 'http://{}:{}'.format(host, port)
base_dir                = os.path.abspath(os.path.dirname(__file__))
cache_dir               = os.path.join(base_dir, 'cache')

# Application settings
template_path           = os.path.join(base_dir, 'web', 'templates')
static_path             = os.path.join(base_dir, 'web', 'static')
static_handler_class    = StaticFileHandler

# Theme
theme                   = 'templatevamp'

# Database settings (default to sqlite)
database_uri            = 'sqlite:///' + os.path.join(base_dir, 'app.db')
