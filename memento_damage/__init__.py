import errno
import io
import json
import logging
import mimetypes
import os
import sys
import tempfile
import time
import urllib
from datetime import datetime
from optparse import OptionParser

from memento_damage.damage_analysis import MementoDamageAnalysis

base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, base_dir)
from memento_damage.tools import Command, rmdir_recursive, prompt_yes_no


class MementoDamage(object):
    background_color = 'FFFFFF'
    viewport_size = [1024, 777]

    _crawljs_script = os.path.join(base_dir, 'phantomjs', 'crawl.js')
    _debug = False
    _info = False
    _mode = 'simple'
    _follow_redirection = False
    _clean_cache = True

    _result = None
    _last_error_message = None

    def __init__(self, uri, output_dir, options={}):
        self.uri = str(uri)
        self.output_dir = output_dir

        self.reformat_uri_webrecorder_io()

        # Initialize variable
        self.app_log_file = os.path.join(self.output_dir, 'app.log')
        self.html_file = os.path.join(self.output_dir, 'source.html')
        self.network_log_file = os.path.join(self.output_dir, 'network.log')
        self.image_log_file = os.path.join(self.output_dir, 'image.log')
        self.css_log_file = os.path.join(self.output_dir, 'css.log')
        self.js_log_file = os.path.join(self.output_dir, 'js.log')
        self.video_log_file = os.path.join(self.output_dir, 'video.log')
        self.text_log_file = os.path.join(self.output_dir, 'text.log')
        self.screenshot_file = os.path.join(self.output_dir, 'screenshot.png')
        self.json_result_file = os.path.join(self.output_dir, 'result.json')

        # options
        if 'mode' in options: self._mode = options['mode']
        if 'redirect' in options: self._follow_redirection = options['redirect']
        if 'debug' in options:
            if options['debug'] == 'complete':
                self._debug = True
            elif options['debug'] == 'simple':
                self._info = True

        # Setup logger --> to show debug verbosity
        log_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # To stdout
        log_stdout_handler = logging.StreamHandler(sys.stdout)
        log_stdout_handler.setFormatter(log_formatter)

        # To file
        log_file_handler = logging.FileHandler(self.app_log_file, mode='w')
        log_file_handler.setFormatter(log_formatter)
        log_file_handler.setLevel(logging.DEBUG)

        # Configure logger
        self.logger = logging.getLogger(uri)
        self.logger.addHandler(log_file_handler)
        self.logger.addHandler(log_stdout_handler)

        self.setup_logger()

    def reformat_uri_webrecorder_io(self):
        if self.uri.startswith('https://webrecorder.io') or self.uri.startswith('http://webrecorder.io'):
            wrc_comps = self.uri.replace('https://webrecorder.io/', '').split('/')
            user, project, date = wrc_comps[:3]
            wrc_url = '/'.join(wrc_comps[3:])
            new_uri = 'https://wbrc.io/{}/{}/{}id_/{}'.format(user, project, date, wrc_url)
            self.uri = new_uri

    def setup_logger(self):
        if self._info:
            self.logger.setLevel(logging.INFO)
        elif self._debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.ERROR)

    def log_stdout(self, out, write_fn):
        if out and hasattr(out, 'readline'):
            for line in iter(out.readline, b''):
                line = line.strip()
                write_fn(line)
        else:
            write_fn(out)

    def log_output(self, msg):
        if 'background_color' in msg:
            msg = json.loads(msg)
            if msg['background_color']:
                self.background_color = msg['background_color']
                return

        if 'crawl-result' in msg:
            msg = json.loads(msg)
            crawl_result = msg['crawl-result']
            self._crawl_result = crawl_result
            msg = crawl_result['message']

        if self.logger.level == logging.DEBUG:
            self.logger.debug(msg)
        elif self.logger.level == logging.INFO:
            self.logger.info(msg)

    def log_stderr(self, out, write_fn):
        if out and hasattr(out, 'readline'):
            for line in iter(out.readline, b''):
                line = line.strip()
                write_fn(line)
        else:
            write_fn(out)

    def log_error(self, msg):
        if 'crawl-result' in msg:
            msg = json.loads(msg)
            crawl_result = msg['crawl-result']
            self._crawl_result = crawl_result

            if crawl_result['error']:
                self.response_time = datetime.now()
                self._last_error_message = crawl_result['message']

                if self._mode == 'simple':
                    self.logger.error(crawl_result['message'])
                elif self._mode == 'json':
                    self.logger.error(json.dumps(crawl_result, indent=4))
                else:
                    self.logger.error('Choose mode "simple" or "json"')
        else:
            self._last_error_message = msg
            self.logger.error(msg)

    def run(self, re_run=True):
        self._result = {}

        # Check mimetype of URI input
        try:
            res = urllib.urlopen(self.uri)
            http_message = res.info()
            mimetype = http_message.type
        except:
            mimetype, encoding = mimetypes.guess_type(self.uri)

        if mimetype and 'html' not in mimetype:
            self._result['uri'] = self.uri
            self._result['error'] = True
            self._result['message'] = 'URI must be in HTML format'
            return

        self.request_time = datetime.now()
        if re_run:
            # Crawl page with phantomjs crawl.js via arguments
            # Equivalent with console:
            phantomjs = os.getenv('PHANTOMJS', 'phantomjs')

            pjs_cmd = [phantomjs, '--ssl-protocol=any', '--ignore-ssl-errors=true', '--output-encoding=utf8',
                       '--web-security=false', self._crawljs_script, self.uri, self.output_dir,
                       str(self._follow_redirection), '{}x{}'.format(*self.viewport_size), str(self.logger.level)]
            cmd = Command(pjs_cmd, pipe_stdout_callback=self.log_stdout, pipe_stderr_callback=self.log_stderr)
            err_code = cmd.run(10 * 60,
                               stdout_callback_args=(self.log_output,),
                               stderr_callback_args=(self.log_error,))

            if err_code != 0:
                self._result['uri'] = self.uri
                self._result['error'] = True
                self._result['message'] = self._last_error_message
            else:
                try:
                    # get result of damage analysis
                    self._result = self._do_analysis()
                    self.response_time = datetime.now()

                    if not self._result['error']:
                        self._result['message'] = 'Calculation is finished in {} seconds'.format(
                            (self.response_time - self.request_time).seconds)
                        self._result['timer'] = {
                            'request_time': (self.request_time - datetime(1970, 1, 1)).total_seconds(),
                            'response_time': (self.response_time - datetime(1970, 1, 1)).total_seconds()
                        }
                        self._result['calculation_time'] = (self.response_time - self.request_time).seconds
                except Exception, e:
                    self._result['uri'] = self.uri
                    self._result['error'] = True
                    self._result['message'] = "Error: {0}".format(str(e))

            # Save output
            io.open(self.json_result_file, 'wb').write(json.dumps(self._result, indent=4))
            self._do_clean_cache()

        else:
            if os.path.exists(self.json_result_file):
                self._result = json.loads(io.open(self.json_result_file).read())

    def get_result(self):
        self._do_close_logger()
        return self._result

    def print_result(self):
        # Print total damage
        if self._result:
            if not self._result['error']:
                if self._mode == 'simple':
                    final_uri = self.uri
                    if len(self._result['redirect_uris']) > 1:
                        final_uri, final_status = self._result['redirect_uris'][len(self._result['redirect_uris']) - 1]
                    print('Total damage of {} is {}'.format(final_uri, str(self._result['total_damage'])))

                elif self._mode == 'json':
                    print(json.dumps(self._result, indent=4))

                else:
                    self.logger.error('Choose mode "simple" or "json"')

            else:
                if self._mode == 'simple':
                    print('Error in processing {}: {}'.format(self.uri, str(self._result['message'])))
                elif self._mode == 'json':
                    print(json.dumps(self._result, indent=4))
                else:
                    self.logger.error('Choose mode "simple" or "json"')

        self._do_close_logger()

    def _do_analysis(self):
        # Calculate damage
        analysis = MementoDamageAnalysis(self)
        analysis.run()

        return analysis.get_result()

    def _do_clean_cache(self):
        # Remove cache directory
        if self._clean_cache:
            time.sleep(3)
            rmdir_recursive(self.output_dir)

    def _do_close_logger(self):
        for h in self.logger.handlers:
            h.flush()
            h.close()
            self.logger.removeHandler(h)

    def set_show_debug_message(self):
        self._debug = True
        self.setup_logger()

    def set_show_info_message(self):
        self._info = True
        self.setup_logger()

    def set_output_mode_json(self):
        self._mode = 'json'

    def set_follow_redirection(self):
        self._follow_redirection = True

    def set_dont_clean_cache_on_finish(self):
        self._clean_cache = False


def main():
    parser = OptionParser()
    parser.set_usage(parser.get_usage().replace('\n', '') + ' <URI>')
    parser.add_option("-o", "--output-dir",
                      dest="output_dir", default=None,
                      help="output directory (optional)")
    parser.add_option("-O", "--overwrite",
                      action="store_true", dest="overwrite", default=False,
                      help="overwrite existing output directory")
    parser.add_option("-m", "--mode",
                      dest="mode", default="simple",
                      help='output mode: "simple" or "json" [default: %default]')
    parser.add_option("-d", "--debug",
                      dest="debug", default=None,
                      help='debug mode: "simple" or "complete" [default: %default]')
    parser.add_option("-L", "--redirect",
                      action="store_true", dest="redirect", default=False,
                      help="follow url redirection")

    (options, args) = parser.parse_args()
    options = vars(options)

    if len(args) < 1:
        parser.print_help()
        exit()

    uri = args[0]
    quoted_url = urllib.quote(uri).replace('/', '_').replace('.', '-')

    use_tempdir = False
    # If option -O is provided, use it
    if options['output_dir']:
        output_dir = options['output_dir']
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(os.getcwd(), output_dir)
            output_dir = os.path.abspath(output_dir)

    # Otherwise make temp dir
    else:
        output_dir = tempfile.mkdtemp()
        use_tempdir = True

    output_dir = os.path.join(output_dir, quoted_url)
    re_run = (not os.path.exists(output_dir)) or (os.path.exists(output_dir) and options['overwrite'])

    # Make output_dir recursive
    try:
        os.makedirs(output_dir)
    except OSError, e:
        if e.errno != errno.EEXIST: raise

    # Instantiate and run
    damage = MementoDamage(uri, output_dir, options)
    if not use_tempdir:
        damage.set_dont_clean_cache_on_finish()
    damage.run(re_run)
    damage.print_result()


if __name__ == "__main__":
    main()
