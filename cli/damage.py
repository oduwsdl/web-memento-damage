import errno
import json
import os
import sys
from hashlib import md5
from optparse import OptionParser

import unicodecsv as csv

import config

base_dir = config.base_dir
sys.path.insert(0, base_dir)
from ext.tools import Command


class CrawlAndCalculateDamage:
    _page = {'background_color': 'FFFFFF'}

    def __init__(self, uri, output_dir, options={}):
        self._uri = uri
        self._output_dir = output_dir
        self._verbose = options.verbose if 'verbose' in options else True
        self._mode = options.mode if 'mode' in options else 'json'

    def log_output(self, out, logger_file, result_file, write_fn):
        if out and hasattr(out, 'readline'):
            for line in iter(out.readline, b''):
                # for line in out.readlines():
                line = line.strip()
                write_fn(logger_file, result_file, line)
        else:
            write_fn(logger_file, result_file, out)

    def write_output(self, logger_file, result_file, line):
        if logger_file: logger_file.write(line + '\n')

        if 'background_color' in line and self._page:
            line = json.loads(line)
            if line['background_color']:
                self._page['background_color'] = line['background_color']
        if 'result' in line:
            try:
                line = json.loads(line)

                result = line['result']
                result['error'] = False
                result['is_archive'] = False

                # Print total damage
                if self._mode == 'simple':
                    print('Total damage of {} is {}'.format(
                        self._uri, str(result['total_damage'])))
                elif self._mode == 'json':
                    print(json.dumps(result))
                else:
                    print('Choose mode "simple" or "json"')

                # Write result to file
                if result_file:
                    with open(result_file, 'a+') as res:
                        res.write(','.join((self._uri, str(result['total_damage']))) + '\n')
            except (ValueError, KeyError) as e:
                if self._verbose: print(line)

        elif self._verbose: print(line)

    def result_error(self, err=''):
        pass

    def do_calculation(self):
        hashed_url = md5(self._uri).hexdigest()

        # Define path of scripts
        crawljs_script = os.path.join(base_dir, 'ext', 'phantomjs', 'crawl.js')
        damage_py_script = os.path.join(base_dir, 'ext', 'damage.py')

        # Define output files location
        crawler_log_file = os.path.join(self._output_dir, 'log', '{}.crawl.log'.format(hashed_url))
        damage_result_file = os.path.join(self._output_dir, 'result.csv')

        try:
            os.makedirs(os.path.join(self._output_dir, 'screenshot'))
            os.makedirs(os.path.join(self._output_dir, 'html'))
            os.makedirs(os.path.join(self._output_dir, 'log'))
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
        cmd = Command(['phantomjs', '--ssl-protocol=any', crawljs_script, self._uri, self._output_dir],
                      self.log_output)
        err_code = cmd.run(10 * 60, args=(logger_file, damage_result_file, self.write_output,))

        if err_code == 0:
            python = sys.executable

            # Calculate damage with damage-old.py via arguments
            # Equivalent with console:
            #   python damage.py <uri> <cache_dir> <bg>
            cmd = Command([python, damage_py_script, self._uri, self._output_dir, self._page['background_color']],
                          self.log_output)

            err_code = cmd.run(10 * 60, args=(logger_file, damage_result_file, self.write_output,))
            if err_code != 0:
                self.result_error()
        else:
            self.result_error()


if __name__ == "__main__":
    parser = OptionParser()
    parser.set_usage(parser.get_usage().replace('\n', '') + ' <uri or csv> <output_dir>')
    parser.add_option("-m", "--mode",
                      dest="mode", default="simple",
                      help="output mode: simple or json [default: %default]")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="print status messages to stdout")

    (options, args) = parser.parse_args()

    if len(args) != 2:
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