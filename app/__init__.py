import pkgutil
import sys

import config
from ext.blueprint import Application
from ext.blueprint import Blueprint

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker


# Instantiate Tornado Application
_settings = Application.import_settings_from_object(config)
application = Application(**_settings)
application.config = _settings

# Instantiate SQLAlchemy ORM (Object Relational Manager)
class _Database(object):
    Model = declarative_base()
    session = None
    def __init__(self):
        self._engine = create_engine(_settings.get('database_uri'), echo=False)
        self.session = scoped_session(sessionmaker(bind=self._engine))

    def create_all(self):
        self.Model.metadata.create_all(self._engine)

database = _Database()

# Scan modules
sys.path.append('app/modules')
for importer, package_name, _ in pkgutil.iter_modules(['app/modules']):
    importer.find_module(package_name).load_module(package_name)

for Cls in Blueprint.__subclasses__():
    application.register_blueprint_class(Cls)

# Create all tables
database.create_all()
