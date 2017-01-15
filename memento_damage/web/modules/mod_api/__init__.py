import errno
import json
import os
from hashlib import md5
from urlparse import urlparse

from flask import Blueprint, request, render_template, \
    Response, current_app as app

from memento_damage import MementoDamage


class API(Blueprint):
    def __init__(self):
        Blueprint.__init__(self, 'api', __name__, url_prefix='/api',
                           template_folder='views',
                           static_folder='static',
                           static_url_path='/static/home')

        @self.route('/', methods=['GET'])
        def api_index():
            parsed_uri = urlparse(request.referrer)
            domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
            return render_template("api_index.html", domain=domain)

        # @self.route('/api/damage/<path:uri>/<string:fresh>', methods=['GET'])
        @self.route('/damage/<path:uri>', methods=['GET'])
        def api_damage(uri):
            fresh = request.args.get('fresh', 'true')
            fresh = False if fresh.lower() == 'false' else True

            hashed_url = md5(uri).hexdigest()
            output_dir = os.path.join(app.config['CACHE_DIR'], hashed_url)

            try:
                os.makedirs(output_dir)
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise

            damage = MementoDamage(uri, output_dir)
            damage.set_follow_redirection()
            damage.set_output_mode_json()
            damage.set_show_debug_message()
            damage.run()

            print damage.get_result()

            return Response(response=json.dumps(damage.get_result()), status=200, mimetype='application/json')
