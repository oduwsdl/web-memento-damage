from flask import Blueprint, render_template


class ContactUs(Blueprint):
    def __init__(self):
        Blueprint.__init__(self, 'contact_us', __name__, url_prefix='/contact_us',
                           template_folder='views',
                           static_folder='static',
                           static_url_path='/static/home')

        @self.route('/', methods=['GET'])
        def api_index():
            return render_template("contact_us_index.html")
