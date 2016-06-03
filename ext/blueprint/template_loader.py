#!/usr/bin/env python3

# The MIT License (MIT)
#
# Copyright (c) 2015 Benedikt Schmitt <benedikt@benediktschmitt.de>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# std
import os

# third party
import tornado.template


class TemplateLoader(tornado.template.BaseLoader):
    """
    This template loader looks up different directories for a template,
    based on a prefix:

    #.  ".index.html"
        Search in the template path of the *current* blueprint.

    #.  "dashboard.index.html"
        Search in the template path of the *dashboard* blueprint for the
        *index.html* file.

    #.  "index.html"
        Search in the global template path for the index.html file.

    To be able to resolve a relative template path (starts with a "."), we need
    to associate each loader with the blueprint.
    """

    def __init__(self, application, blueprint=None, **kargs):
        """
        """
        super(TemplateLoader, self).__init__(**kargs)
        self.application = application
        self.blueprint = blueprint
        return None

    def resolve_path(self, name, parent_path = None):
        """
        Simply returns the template name. Each template is either in the
        blueprint's template path or the application's tempalte path.
        """
        if name.startswith("."):
            name = self.blueprint.name + name
        return name

    def _create_template(self, name):
        """
        """
        # Check if the substring before the first "." in *name* is a blueprint
        # name.
        if name[:name.find(".")] in self.application.blueprints:
            blueprint_name, filename = name.split(".", 1)
            blueprint = self.application.blueprints[blueprint_name]

            template_path = os.path.join(
                blueprint.settings.get("template_path"), filename
            )
        # There is no blueprint prefix in the name. So we use the application's
        # template folder.
        else:
            template_path = os.path.join(
                self.application.settings.get("template_path"), name
            )

        # Load the template.
        with open(template_path, "rb") as file:
            template = tornado.template.Template(
                file.read(), name=name, loader=self
            )
        return template
