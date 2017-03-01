from flask import Blueprint, render_template


class FAQ(Blueprint):
    def __init__(self):
        Blueprint.__init__(self, 'faq', __name__, url_prefix='/faq',
                           template_folder='views',
                           static_folder='static',
                           static_url_path='/static/home')

        @self.route('/', methods=['GET'])
        def api_index():
            return render_template("faq_index.html")
