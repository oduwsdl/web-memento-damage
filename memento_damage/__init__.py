import errno
import io
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime
from hashlib import md5
from optparse import OptionParser

from memento_damage.damage_analysis import MementoDamageAnalysis

base_dir = os.path.join(os.path.dirname(__file__))
base_dir = os.path.abspath(base_dir)
sys.path.insert(0, base_dir)
from memento_damage.tools import Command, rmdir_recursive


class MementoDamage(object):
    # Define all output files
    APP_LOG_FILE_NAME = 'app.log'
    HTML_FILE_NAME = 'source.html'
    NETWORK_LOG_FILE_NAME = 'network.log'
    IMAGE_LOG_FILE_NAME = 'image.log'
    CSS_LOG_FILE_NAME = 'css.log'
    VIDEO_LOG_FILE_NAME = 'video.log'
    SCREENSHOT_FILE_NAME = 'screenshot.png'
    JSON_RESULT_FILE_NAME = 'result.json'

    background_color = 'FFFFFF'

    _crawljs_script = os.path.join(base_dir, 'phantomjs', 'crawl.js')
    _debug = False
    _info = False
    _mode = 'simple'
    _follow_redirection = False
    _clean_cache = True

    _result = None

    def __init__(self, uri, output_dir, options={}):
        self.uri = str(uri)
        self.output_dir = output_dir

        # Initialize variable
        self.app_log_file = os.path.join(self.output_dir, self.APP_LOG_FILE_NAME)
        self.html_file = os.path.join(self.output_dir, self.HTML_FILE_NAME)
        self.network_log_file = os.path.join(self.output_dir, self.NETWORK_LOG_FILE_NAME)
        self.image_log_file = os.path.join(self.output_dir, self.IMAGE_LOG_FILE_NAME)
        self.css_log_file = os.path.join(self.output_dir, self.CSS_LOG_FILE_NAME)
        self.video_log_file = os.path.join(self.output_dir, self.VIDEO_LOG_FILE_NAME)
        self.screenshot_file = os.path.join(self.output_dir, self.SCREENSHOT_FILE_NAME)
        self.json_result_file = os.path.join(self.output_dir, self.JSON_RESULT_FILE_NAME)

        # options
        if 'debug' in options: self._debug = options['debug']
        if 'info' in options: self._info = options['info']
        if 'mode' in options: self._mode = options['mode']
        if 'redirect' in options: self._follow_redirection = options['redirect']

        # Setup logger --> to show debug verbosity
        log_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # To stdout
        log_stdout_handler = logging.StreamHandler(sys.stdout)
        log_stdout_handler.setFormatter(log_formatter)

        # To file
        log_file_handler = logging.FileHandler(self.app_log_file)
        log_file_handler.setFormatter(log_formatter)

        # Configure logger
        self.logger = logging.getLogger(uri)
        self.logger.addHandler(log_file_handler)
        self.logger.addHandler(log_stdout_handler)

        self.setup_logger()

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
        if self.logger.level == logging.DEBUG: self.logger.debug(msg)
        elif self.logger.level == logging.INFO: self.logger.info(msg)

        if 'background_color' in msg:
            msg = json.loads(msg)
            if msg['background_color']:
                self.background_color = msg['background_color']

        if 'crawl_result' in msg:
            msg = json.loads(msg)
            crawl_result = msg['crawl_result']
            self._crawl_result = crawl_result

            if crawl_result['error']:
                self.response_time = datetime.now()

                if self._mode == 'simple':
                    self.logger.error(crawl_result['message'])
                elif self._mode == 'json':
                    self.logger.error(json.dumps(crawl_result, indent=4))
                else:
                    self.logger.error('Choose mode "simple" or "json"')

    def log_stderr(self, out, write_fn):
        if out and hasattr(out, 'readline'):
            for line in iter(out.readline, b''):
                line = line.strip()
                write_fn(line)
        else:
            write_fn(out)

    def log_error(self, msg):
        self.logger.error(msg)

    def run(self):
        self.request_time = datetime.now()

        # Crawl page with phantomjs crawl.js via arguments
        # Equivalent with console:
        phantomjs = os.getenv('PHANTOMJS', 'phantomjs')

        pjs_cmd = [phantomjs, '--ssl-protocol=any', self._crawljs_script, self.uri, self.output_dir,
                   str(self._follow_redirection), str(self.logger.level)]
        cmd = Command(pjs_cmd, pipe_stdout_callback=self.log_stdout, pipe_stderr_callback=self.log_stderr)
        err_code = cmd.run(10 * 60,
                           stdout_callback_args=(self.log_output, ),
                           stderr_callback_args=(self.log_error, ))

        if err_code != 0:
            self.log_error('Application closed unexpectedly')
            self._do_clean_cache()
            return

        # get result of damage analysis
        self._result = self._do_analysis()
        self.response_time = datetime.now()

        self._result['message'] = 'Calculation is finished in {} seconds'.format(
            (self.response_time - self.request_time).seconds)
        self._result['timer'] = {
            'request_time': (self.request_time - datetime(1970, 1, 1)).total_seconds(),
            'response_time': (self.response_time - datetime(1970, 1, 1)).total_seconds()
        }
        self._result['calculation_time'] = (self.response_time - self.request_time).seconds

        # Save output
        io.open(self.json_result_file, 'wb').write(json.dumps(self._result))

        self._do_clean_cache()
        return self._result

    def get_result(self):
        return self._result

    def print_result(self):
        # Print total damage
        if self._result:
            if self._mode == 'simple':
                print('Total damage of {} is {}'.format(self.uri, str(self._result['total_damage'])))
            elif self._mode == 'json':
                print(json.dumps(self._result, indent=4))
            else:
                self.logger.error('Choose mode "simple" or "json"')

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
    parser.add_option("-O", "--output-dir",
                      dest="output_dir", default=None,
                      help="output directory (optional)")
    parser.add_option("-m", "--mode",
                      dest="mode", default="simple",
                      help="output mode: simple or json [default: %default]")
    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug", default=False,
                      help="print debug messages")
    parser.add_option("-i", "--info",
                      action="store_true", dest="info", default=False,
                      help="print info messages")
    parser.add_option("-L", "--redirect",
                      action="store_true", dest="redirect", default=False,
                      help="follow url redirection")

    (options, args) = parser.parse_args()
    options = vars(options)

    if len(args) < 1:
        parser.print_help()
        exit()

    uri = args[0]

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

    hashed_url = md5(uri).hexdigest()
    output_dir = os.path.join(output_dir, hashed_url)

    # Make output_dir recursive
    try:
        os.makedirs(output_dir)
    except OSError, e:
        if e.errno != errno.EEXIST: raise

    # Instantiate and run
    damage = MementoDamage(uri, output_dir, options)
    if not use_tempdir:
        damage.set_dont_clean_cache_on_finish()
    damage.run()
    damage.print_result()

if __name__ == "__main__":
    main()