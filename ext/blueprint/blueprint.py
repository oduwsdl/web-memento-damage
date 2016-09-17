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
import hashlib
import inspect
import os

import tornado
from .request_handler import RequestHandler, StaticFileHandler


class Blueprint(object):
    """
    This is the blueprint class. It has a similar interface to a tornado
    application, but must be registered on the root application later.
    """

    instance = None
    application = None

    def __init__(self, name=None, url_prefix="", template_path=None,
                 static_path=None, **settings):
        """
        """
        # The unique name of the blueprint. Used internally to resolve
        # addresses and paths (especially templates).
        self.application = settings.get('application')
        self.instance = self
        self.url_prefix = url_prefix

        if name:
            self.name = name
        else:
            self.name = self.__class__.__name__

        # todo:
        #   This dictionary should extend the application settings.
        self.settings = settings

        # Set template_path and static_path automatically
        if template_path:
            self.settings['template_path'] = template_path
        else:
            self.settings['template_path'] = os.path.join(os.path.abspath(
                            os.path.dirname(inspect.getfile(self.__class__))),
                            "templates", self.application.config['theme'])

        if static_path:
            self.settings['static_path'] = static_path
        else:
            self.settings['static_path'] = os.path.join(os.path.abspath(
                            os.path.dirname(inspect.getfile(self.__class__))),
                            "static")

        self.settings['static_url_prefix'] = '/{}/static/'.format(self.name.lower())

        self._handlers = list()
        self.scan_handlers()

    def add_handlers(self, host_pattern, host_handlers):
        """
        """
        self._handlers.extend(
            (host_pattern, handler) for handler in host_handlers
        )

    def scan_handlers(self):
        self.add_handlers('.*', [
            tornado.web.url(r"{}(.*)".format(self.settings['static_url_prefix']),
                            StaticFileHandler,
                            { 'path' : self.settings['static_path'] },
                            name=StaticFileHandler.__name__)
        ])

        for Cls in RequestHandler.__subclasses__():
            if str(Cls.__module__).startswith(self.__class__.__module__):
                if not Cls.name:
                    Cls.name = Cls.__name__

                url = Cls.route
                if isinstance(url, basestring) or isinstance(url, unicode):
                    url = [url, ]

                kwargs = Cls.kwargs if hasattr(Cls, 'kwargs') else {}

                handlers = []
                for u in url:
                    handlers.append(
                        tornado.web.url(u, Cls, kwargs, name=Cls.name))
                self.add_handlers('.*', handlers)
