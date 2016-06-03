import pkgutil
import sys

import config
from ext.blueprint import Application
from ext.blueprint import Blueprint

settings = Application.import_settings_from_object(config)

application = Application(**settings)

sys.path.append('app/modules')
for importer, package_name, _ in pkgutil.iter_modules(['app/modules']):
    importer.find_module(package_name).load_module(package_name)

for Cls in Blueprint.__subclasses__():
    application.register_blueprint_class(Cls)
