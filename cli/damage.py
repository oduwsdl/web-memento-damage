import errno
import json
import os
import sys
from datetime import datetime
from hashlib import md5
from optparse import OptionParser

import unicodecsv as csv

base_dir = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, base_dir)
from ext.tools import Command


class CrawlAndCalculateDamage:
    _page = {'background_color': 'FFFFFF'}
    _verbose = False
    _show_step = False
    _mode = 'simple'
    _follow_redirection = False

    def __init__(self, uri, output_dir, options={}):
        self._uri = uri
        self._output_dir = output_dir
        if 'show_step' in options: self._show_step = options['show_step']
        if 'verbose' in options: self._verbose = options['verbose']
        if 'mode' in options: self._mode = options['mode']
        if 'redirect' in options: self._follow_redirection = options['redirect']

        hashed_url = md5(self._uri).hexdigest()
        try:
            os.makedirs(os.path.join(self._output_dir, hashed_url))
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise

    def log_output(self, out, logger_file, result_file, summary_file, write_fn):
        if out and hasattr(out, 'readline'):
            for line in iter(out.readline, b''):
                # for line in out.readlines():
                line = line.strip()
                write_fn(logger_file, result_file, summary_file, line)
        else:
            write_fn(logger_file, result_file, summary_file, out)

    def write_output(self, logger_file, result_file, summary_file, line):
        if logger_file: logger_file.write(line + '\n')
        if self._verbose: print('DEBUG: {} - {}'.format(datetime.now(), line))

        if 'background_color' in line and self._page:
            line = json.loads(line)
            if line['background_color']:
                self._page['background_color'] = line['background_color']

        if 'crawl-result' in line:
            line = json.loads(line)
            crawl_result = line['crawl-result']
            self._crawl_result = crawl_result

            if crawl_result['error']:
                self.response_time = datetime.now()

                if self._mode == 'simple':
                    print(crawl_result['message'])
                elif self._mode == 'json':
                    print(json.dumps(crawl_result, indent=4))
                else:
                    print('Choose mode "simple" or "json"')

        if 'result' in line:
            try:
                self.response_time = datetime.now()

                line = json.loads(line)

                result = line['result']
                result.update(self._crawl_result)
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
                    print('Total damage of {} is {}'.format(
                        self._uri, str(result['total_damage'])))
                elif self._mode == 'json':
                    print(json.dumps(result, indent=4))
                else:
                    print('Choose mode "simple" or "json"')

                # Write result to file
                if result_file:
                    with open(result_file, 'w') as f:
                        f.write(json.dumps(result))
                        f.flush()
                        f.close()

                if summary_file:
                    with open(summary_file, 'a+') as f:
                        f.write(','.join((self._uri, str(result['total_damage']))) + '\n')
                        f.flush()
                        f.close()

            except (ValueError, KeyError) as e: pass

    def result_error(self, err=''):
        pass

    def do_calculation(self):
        self.request_time = datetime.now()
        hashed_url = md5(self._uri).hexdigest()

        # Define path of scripts
        crawljs_script = os.path.join(base_dir, 'ext', 'phantomjs', 'crawl.js')
        damage_py_script = os.path.join(base_dir, 'ext', 'damage.py')

        # Define output files location
        crawler_log_file = os.path.join(self._output_dir, hashed_url, 'crawl.log')
        damage_result_file = os.path.join(self._output_dir, hashed_url, 'result.json')
        damage_summary_file = os.path.join(self._output_dir, 'result.csv')

        try:
            os.makedirs(os.path.abspath(os.path.join(crawler_log_file, os.pardir)))
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise

        # Define logger writer
        logger_file = open(crawler_log_file, 'w')
        logger_file.write('')
        logger_file.close()

        logger_file = open(crawler_log_file, 'a')

        # Crawl page with phantomjs crawl.js via arguments
        # Equivalent with console:
        cmd = Command(['phantomjs', '--ssl-protocol=any', crawljs_script, self._uri, self._output_dir,
                       str(self._follow_redirection)], self.log_output)

        if self._show_step: print('DEBUG: {} == Start Crawling =='.format(datetime.now()))
        err_code = cmd.run(10 * 60, args=(logger_file, damage_result_file, damage_summary_file, self.write_output,))
        if self._show_step: print('DEBUG: {} == Finish Crawling =='.format(datetime.now()))

        if err_code == 0:
            python = sys.executable

            # Calculate damage with damage-old.py via arguments
            # Equivalent with console:
            #   python damage.py <uri> <cache_dir> <bg>
            cmd = Command([python, damage_py_script, self._uri, self._output_dir, self._page['background_color']],
                          self.log_output)

            if self._show_step: print('DEBUG: {} == Start Analyzing =='.format(datetime.now()))
            err_code = cmd.run(10 * 60, args=(logger_file, damage_result_file, damage_summary_file, self.write_output,))
            if self._show_step: print('DEBUG: {} == Finish Analyzing =='.format(datetime.now()))

            if err_code != 0:
                self.result_error()
        else:
            self.result_error()


if __name__ == "__main__":
    parser = OptionParser()
    parser.set_usage(parser.get_usage().replace('\n', '') + ' <URI> <output_dir>')
    parser.add_option("-m", "--mode",
                      dest="mode", default="simple",
                      help="output mode: simple or json [default: %default]")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="print status messages to stdout")
    parser.add_option("-t", "--show-step",
                      action="store_true", dest="show_step", default=False,
                      help="print step messages to stdout")
    parser.add_option("-L", "--redirect",
                      action="store_true", dest="redirect", default=False,
                      help="follow url redirection")

    (options, args) = parser.parse_args()
    options = vars(options)

    if len(args) < 2:
        parser.print_help()
        exit()

    uri = args[0]
    output_dir = args[1]
    output_dir = os.path.abspath(output_dir)

    damage = CrawlAndCalculateDamage(uri, output_dir, options)

    if os.path.isfile(uri):
        with open(uri) as f:
            for row in csv.reader(f):
                uri = row[0]
                damage.do_calculation()
    else:
        damage.do_calculation()