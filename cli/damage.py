import errno
import json
import logging
import os
import sys
import time
from datetime import datetime
from hashlib import md5
from optparse import OptionParser

base_dir = os.path.join(os.path.dirname(__file__), os.pardir)
base_dir = os.path.abspath(base_dir)
sys.path.insert(0, base_dir)
from ext.tools import Command, rmdir_recursive


class CrawlAndCalculateDamage:
    _crawljs_script = os.path.join(base_dir, 'ext', 'phantomjs', 'crawl.js')
    _damage_py_script = os.path.join(base_dir, 'ext', 'damage.py')
    _page = {'background_color': 'FFFFFF'}
    _debug = False
    _info = False
    _mode = 'simple'
    _follow_redirection = False
    _clean_cache = True

    def __init__(self, uri, output_dir, options={}):
        self._uri = uri
        self._output_dir = output_dir

        # Setup options
        if 'debug' in options: self._debug = options['debug']
        if 'info' in options: self._info = options['info']
        if 'mode' in options: self._mode = options['mode']
        if 'redirect' in options: self._follow_redirection = options['redirect']
        if 'clean_cache' in options: self._clean_cache = options['clean_cache']

        # Setup logger --> to show debug verbosity
        log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

        # To stdout
        log_stdout_handler = logging.StreamHandler(sys.stdout)
        log_stdout_handler.setFormatter(log_formatter)

        # To file
        app_log_file = os.path.join(self._output_dir, 'app.log')
        log_file_handler = logging.FileHandler(app_log_file)
        log_file_handler.setFormatter(log_formatter)

        # Configure logger
        self._logger = logging.getLogger(uri)
        self._logger.addHandler(log_file_handler)
        self._logger.addHandler(log_stdout_handler)

        if self._info:
            self._logger.setLevel(logging.INFO)
        elif self._debug:
            self._logger.setLevel(logging.DEBUG)
        else:
            self._logger.setLevel(logging.ERROR)

    def log_stdout(self, out, write_fn, result_file):
        if out and hasattr(out, 'readline'):
            for line in iter(out.readline, b''):
                line = line.strip()
                write_fn(line, result_file)
        else:
            write_fn(out, result_file)

    def log_output(self, msg, result_file):
        if self._logger.level == logging.DEBUG: self._logger.debug(msg)
        elif self._logger.level == logging.INFO: self._logger.info(msg)

        if 'background_color' in msg:
            msg = json.loads(msg)
            if msg['background_color']:
                self._page['background_color'] = msg['background_color']

        if 'crawl_result' in msg:
            msg = json.loads(msg)
            crawl_result = msg['crawl_result']
            self._crawl_result = crawl_result

            if crawl_result['error']:
                self.response_time = datetime.now()

                if self._mode == 'simple':
                    self._logger.error(crawl_result['message'])
                elif self._mode == 'json':
                    self._logger.error(json.dumps(crawl_result, indent=4))
                else:
                    self._logger.error('Choose mode "simple" or "json"')

        if 'result' in msg:
            try:
                self.response_time = datetime.now()

                msg = json.loads(msg)

                result = msg['result']
                # result.update(self._crawl_result)
                result['error'] = False
                result['is_archive'] = False
                result['message'] = 'Calculation is finished in {} seconds'.format(
                    (self.response_time - self.request_time).seconds
                )
                result['timer'] = {
                    'request_time': (self.request_time - datetime(1970,1,1)).total_seconds(),
                    'response_time': (self.response_time - datetime(1970,1,1)).total_seconds()
                }
                result['calculation_time'] = (self.response_time - self.request_time).seconds

                # Print total damage
                if self._mode == 'simple':
                    self._logger.info('Total damage of {} is {}'.format(
                        self._uri, str(result['total_damage'])))
                elif self._mode == 'json':
                    print(json.dumps(result, indent=4))
                else:
                    self._logger.error('Choose mode "simple" or "json"')

                # Write result to file
                if result_file:
                    with open(result_file, 'w') as f:
                        f.write(json.dumps(result))
                        f.flush()
                        f.close()

            except (ValueError, KeyError) as e: pass

    def log_stderr(self, out, write_fn):
        if out and hasattr(out, 'readline'):
            for line in iter(out.readline, b''):
                line = line.strip()
                write_fn(line)
        else:
            write_fn(out)

    def log_error(self, msg):
        self._logger.error(msg)

    def run(self):
        self.request_time = datetime.now()

        # Define output files location
        damage_result_file = os.path.join(self._output_dir, 'result.json')

        # Crawl page with phantomjs crawl.js via arguments
        # Equivalent with console:
        phantomjs = os.getenv('PHANTOMJS', 'phantomjs')

        pjs_cmd = [phantomjs, '--ssl-protocol=any', self._crawljs_script, self._uri, self._output_dir,
                   str(self._follow_redirection), str(self._logger.level)]
        cmd = Command(pjs_cmd, pipe_stdout_callback=self.log_stdout, pipe_stderr_callback=self.log_stderr)
        err_code = cmd.run(10 * 60,
                           stdout_callback_args=(self.log_output, damage_result_file, ),
                           stderr_callback_args=(self.log_error, ))

        if err_code == 0:
            # Use the same python with this script
            python = sys.executable

            # Calculate damage with damage-old.py via arguments
            # Equivalent with console:
            #   python damage.py <uri> <cache_dir> <bg>
            py_damage_cmd = [python, self._damage_py_script, self._uri, self._output_dir, self._page['background_color']]
            cmd = Command(py_damage_cmd, pipe_stdout_callback=self.log_stdout, pipe_stderr_callback=self.log_stderr)
            err_code = cmd.run(10 * 60,
                               stdout_callback_args=(self.log_output, damage_result_file, ),
                               stderr_callback_args=(self.log_error, ))

            if err_code != 0:
                self.log_error('Application closed unexpectedly')
        else:
            self.log_error('Application closed unexpectedly')

        # Remove cache directory
        if self._clean_cache:
            time.sleep(3)
            rmdir_recursive(self._output_dir)


def main():
    parser = OptionParser()
    parser.set_usage(parser.get_usage().replace('\n', '') + ' <URI> <output_dir>')
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
    parser.add_option("-k", "--keep-cache",
                      action="store_false", dest="clean_cache", default=True,
                      help="dont clean cache after process finished")

    (options, args) = parser.parse_args()
    options = vars(options)

    if len(args) < 2:
        parser.print_help()
        exit()

    uri = args[0]
    hashed_url = md5(uri).hexdigest()
    output_dir = args[1]

    if not os.path.isabs(output_dir):
        output_dir = os.path.join(os.getcwd(), output_dir)
        output_dir = os.path.abspath(output_dir)

    output_dir = os.path.join(output_dir, hashed_url)

    try:
        os.makedirs(output_dir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise

    damage = CrawlAndCalculateDamage(uri, output_dir, options)
    damage.run()


if __name__ == "__main__":
    main()