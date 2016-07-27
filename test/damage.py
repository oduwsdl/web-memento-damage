#!../env-linux/bin/python

import json
import sys
import errno
import os
from hashlib import md5
import unicodecsv as csv

basedir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, basedir)

from ext.tools import Command

if len(sys.argv) != 3:
    print('Usage :')
    print('python test/damage.py <uri> <output_dir>')
    exit()

uri = sys.argv[1]
hashed_url = md5(uri).hexdigest()
output_dir = sys.argv[2]


# Define path for each arguments of crawl.js
crawljs_script = os.path.join(
    basedir, 'ext', 'phantomjs', 'crawl.js'
)
# Define damage.py location
damage_py_script = os.path.join(
    basedir, 'ext', 'damage.py'
)

# Define arguments
screenshot_file = '{}.png'.format(os.path.join(
    output_dir, 'screenshot', hashed_url))
html_file = '{}.html'.format(os.path.join(
    output_dir, 'html', hashed_url))
log_file = '{}.log'.format(os.path.join(
    output_dir, 'log', hashed_url))
images_log_file = '{}.img.log'.format(os.path.join(
    output_dir, 'log', hashed_url))
csses_log_file = '{}.css.log'.format(os.path.join(
    output_dir, 'log', hashed_url))
crawler_log_file = '{}.crawl.log'.format(os.path.join(
    output_dir, 'log', hashed_url))
damage_result_file = '{}result.csv'.format(output_dir)

try:
    os.makedirs(os.path.join(output_dir, 'screenshot'))
    os.makedirs(os.path.join(output_dir, 'html'))
    os.makedirs(os.path.join(output_dir, 'log'))
except OSError, e:
    if e.errno != errno.EEXIST:
        raise

# Logger
f = open(crawler_log_file, 'w')
f.write('')
f.close()

f = open(crawler_log_file, 'a')

def log_output(out, page=None):
    def write(line):
        f.write(line + '\n')
        print(line)

        if 'background_color' in line and page:
            page['background_color'] = json.loads(line)\
                                       ['background_color']
        if 'result' in line:
            line = json.loads(line)

            result = line['result']
            result['error'] = False
            result['is_archive'] = False

            # Write result to file
            with open(damage_result_file, 'a+') as res:
                res.write(','.join((uri, str(result['total_damage']))) + '\n')

    if out and hasattr(out, 'readline'):
        for line in iter(out.readline, b''):
            #for line in out.readlines():
            line =  line.strip()
            write(line)
    else:
        write(out)

# Error
def result_error(err = ''):
    pass

# page background-color will be set from phantomjs result
page = {
    'background_color': 'FFFFFF'
}

# Crawl page with phantomjs crawl.js via arguments
# Equivalent with console:
#   phantomjs crawl.js <screenshot> <html> <log>
cmd = Command(['phantomjs', '--ssl-protocol=any', crawljs_script,
               uri, screenshot_file, html_file, log_file],
              log_output)
err_code = cmd.run(10 * 60, args=(page, ))

if err_code == 0:
    # Calculate damage with damage.py via arguments
    # Equivalent with console:
    #   python damage.py <img_log> <css_log> <screenshot_log> <bg>
    python = sys.executable

    cmd = Command([python, damage_py_script, images_log_file,
                   csses_log_file, screenshot_file,
                   page['background_color']],
                  log_output)
    err_code = cmd.run(10 * 60)
    if err_code != 0:
        result_error()
else:
    result_error()
