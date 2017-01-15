from urlparse import urlparse

from flask import Blueprint, request, render_template


class Home(Blueprint):
    def __init__(self):
        Blueprint.__init__(self, 'home', __name__, url_prefix='',
                           template_folder='views',
                           static_folder='static',
                           static_url_path='/static/home')

        @self.route('/', methods=['GET'])
        @self.route('/memento/', methods=['GET'])
        def home_index():
            return render_template("home_index.html")


        @self.route('/memento/check/', methods=['GET'])
        def home_check():
            url = request.args.get('url')
            fresh = request.args.get('fresh') or 'false'

            if not urlparse(url).scheme:
                self.redirect('/memento/check?url=http://{}&type={}&fresh={}'.format(
                    url, type, fresh
                ))

            return render_template("home_check.html", url=url, type='uri-m', fresh=fresh)
            