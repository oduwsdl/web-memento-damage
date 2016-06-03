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

# third party
import tornado
import tornado.web


class Application(tornado.web.Application):
    """
    Extends the standard :class:`tornado.web.Application` by a method to
    register blueprints.
    """

    def __init__(self, *args, **kargs):
        """
        """
        super(Application, self).__init__(*args, **kargs)
        self.blueprints = dict()

    @classmethod
    def import_settings_from_object(cls, config):
        vars = [item for item in dir(config) if not item.startswith("__")]
        settings = dict()
        for i, var in enumerate(vars):
            settings[var] = eval('config.{}'.format(var))

        return settings

    def register_blueprint(self, blueprint):
        """
        Registers a blueprint and it's handlers on the application.
        """
        assert blueprint.name not in self.blueprints
        self.blueprints[blueprint.name] = blueprint

        for host_pattern, spec in blueprint._handlers:

            # Make sure, the request handlers always receive the blueprint,
            # they are registered on as argument.
            spec.kwargs["blueprint"] = blueprint

            spec = tornado.web.url(
                pattern = blueprint.url_prefix + spec.regex.pattern,
                handler = spec.handler_class,
                kwargs = spec.kwargs,
                name = blueprint.name + "." + spec.name
            )

            self.add_handlers(host_pattern, [spec])

    def register_blueprint_class(self, Cls):
        """
        Registers a blueprint and it's handlers on the application.
        """
        blueprint = Cls(application=self)

        assert blueprint.name not in self.blueprints
        self.blueprints[blueprint.name] = blueprint

        for host_pattern, spec in blueprint._handlers:

            # Make sure, the request handlers always receive the blueprint,
            # they are registered on as argument.
            spec.kwargs["blueprint"] = blueprint

            spec = tornado.web.url(
                pattern = blueprint.url_prefix + spec.regex.pattern,
                handler = spec.handler_class,
                kwargs = spec.kwargs,
                name = blueprint.name + "." + spec.name
            )

            self.add_handlers(host_pattern, [spec])
