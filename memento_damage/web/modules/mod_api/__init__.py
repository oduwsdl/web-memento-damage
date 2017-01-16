import errno
import json
import os
from datetime import datetime
from hashlib import md5
from urlparse import urlparse

from flask import Blueprint, request, render_template, \
    Response, current_app as app
from sqlalchemy import desc

from memento_damage import MementoDamage
from memento_damage.web.models.memento import MementoModel


class API(Blueprint):
    def __init__(self):
        Blueprint.__init__(self, 'api', __name__, url_prefix='/api',
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

            return render_template("api_index.html", domain=domain)

        # @self.route('/api/damage/<path:uri>/<string:fresh>', methods=['GET'])
        @self.route('/damage/<path:uri>', methods=['GET'])
        def api_damage(uri):
            fresh = request.args.get('fresh', 'false')
            fresh = True if fresh.lower() == 'true' else False

            hashed_url = md5(uri).hexdigest()
            output_dir = os.path.join(app.config['CACHE_DIR'], hashed_url)

            try:
                os.makedirs(output_dir)
            except OSError, e:
                if e.errno != errno.EEXIST: raise

                # If fresh == True, do fresh calculation
                if fresh:
                    result = self.do_fresh_calculation(uri, hashed_url, output_dir)
                else:
                    # If there are calculation history, use it
                    last_calculation = self.check_calculation_archives(hashed_url)
                    if last_calculation:
                        result = last_calculation.result
                        time = last_calculation.response_time

                        result = json.loads(result)
                        result['is_archive'] = True
                        result['archive_time'] = time.isoformat()
                        # result['calculation_time'] = (self.end_time - self.start_time).seconds
                    else:
                        result = self.do_fresh_calculation(uri, hashed_url, output_dir)

            return Response(response=json.dumps(result), status=200, mimetype='application/json')

    def check_calculation_archives(self, hashed_uri):
        last_calculation = MementoModel.query\
            .filter(MementoModel.hashed_uri == hashed_uri) \
            .order_by(desc(MementoModel.response_time)) \
            .first()

        return last_calculation

    def do_fresh_calculation(self, uri, hashed_url, output_dir):
        # Instantiate MementoModel
        model = MementoModel()
        model.uri = uri
        model.hashed_uri = hashed_url
        model.request_time = datetime.now()

        damage = MementoDamage(uri, output_dir)
        damage.set_follow_redirection()
        damage.set_output_mode_json()
        damage.set_show_debug_message()
        damage.run()
        result = damage.get_result()

        model.response_time = datetime.now()
        model.result = json.dumps(result)

        try:
            app.db.session.add(model)
            app.db.session.commit()
        except: pass

        return result
