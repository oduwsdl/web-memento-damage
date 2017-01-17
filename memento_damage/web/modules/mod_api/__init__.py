import errno
import io
import json
import os
from datetime import datetime
from hashlib import md5
from urlparse import urlparse

from PIL import Image
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

        @self.route('/damage/progress/<path:uri>', methods=['GET'])
        def api_damage_progress(uri):
            start = request.args.get('start', '0')
            start = int(start)
            hashed_uri = md5(uri).hexdigest()

            app_log_file = os.path.join(app.config['CACHE_DIR'], hashed_uri, 'app.log')
            with open(app_log_file, 'rb') as f:
                lines_to_send = []
                for idx, line in enumerate(f.readlines()):
                    if idx >= start:
                        lines_to_send.append(line.strip())

                return Response(response='\n'.join(lines_to_send), status=200, mimetype='text/plain')

        @self.route('/damage/error/<path:uri>', methods=['GET'])
        def api_damage_error(uri):
            hashed_uri = md5(uri).hexdigest()

            app_log_file = os.path.join(app.config['CACHE_DIR'], hashed_uri, 'app.log')
            return Response(response=json.dumps({'error': False}), status=200, mimetype='application/json')

            # with open(app_log_file, 'rb') as f:
            #     for idx, line in enumerate(f.readlines()):
            #         if 'crawl-result' in line:
            #             json_line = json.loads(line)
            #             self.write(json.dumps(json_line['crawl-result']))
            #             self.finish()
            #
            #     if not self._finished:
            #         self.write(json.dumps({'error': False}))
            #         self.finish()

        @self.route('/damage/screenshot/<path:uri>', methods=['GET'])
        def api_damage_screenshot(uri):
            hashed_uri = md5(uri).hexdigest()

            screenshot_file = os.path.join(app.config['CACHE_DIR'], hashed_uri, 'screenshot.png')
            f = Image.open(screenshot_file)
            o = io.BytesIO()
            f.save(o, format="JPEG")
            s = o.getvalue()

            return Response(response=s, status=200, mimetype='image/png')

        # @self.route('/api/damage/<path:uri>/<string:fresh>', methods=['GET'])
        @self.route('/damage/<path:uri>', methods=['GET'])
        def api_damage(uri):
            fresh = request.args.get('fresh', 'false')
            fresh = True if fresh.lower() == 'true' else False

            hashed_uri = md5(uri).hexdigest()
            output_dir = os.path.join(app.config['CACHE_DIR'], hashed_uri)

            try:
                os.makedirs(output_dir)
            except OSError, e:
                if e.errno != errno.EEXIST: raise

            # If fresh == True, do fresh calculation
            if fresh:
                result = self.do_fresh_calculation(uri, hashed_uri, output_dir)
            else:
                # If there are calculation history, use it
                last_calculation = self.check_calculation_archives(hashed_uri)
                if last_calculation:
                    result = last_calculation.result
                    time = last_calculation.response_time

                    result = json.loads(result)
                    result['is_archive'] = True
                    result['archive_time'] = time.isoformat()
                    # result['calculation_time'] = (self.end_time - self.start_time).seconds
                else:
                    result = self.do_fresh_calculation(uri, hashed_uri, output_dir)

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

        # Do crawl and damage calculation
        damage = MementoDamage(uri, output_dir)
        damage.set_follow_redirection()
        damage.set_output_mode_json()
        damage.set_show_debug_message()
        damage.set_dont_clean_cache_on_finish()
        damage.run()

        result = damage.get_result()

        model.response_time = datetime.now()
        model.result = json.dumps(result)

        try:
            app.db.session.add(model)
            app.db.session.commit()
        except: pass

        return result
