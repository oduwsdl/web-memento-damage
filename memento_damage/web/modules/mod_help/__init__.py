from urlparse import urlparse

from flask import Blueprint, request, render_template, \
    current_app as app


class Help(Blueprint):
    def __init__(self):
        Blueprint.__init__(self, 'help', __name__, url_prefix='/help',
                           template_folder='views',
                           static_folder='static',
                           static_url_path='/static/home')

        @self.route('/', methods=['GET'])
        def api_index():
            try:
                parsed_uri = urlparse(request.referrer)
                domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
            except:
                domain = app.config['BASE_URL'] + '/'

            return render_template("help_index.html", domain=domain)
