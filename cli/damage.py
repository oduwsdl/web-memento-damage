import json
import sys
import errno
import os
from hashlib import md5
import unicodecsv as csv

basedir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..'
    ))
sys.path.insert(0, basedir)
from ext.tools import Command


def log_output(out, write_fn):
    if out and hasattr(out, 'readline'):
        for line in iter(out.readline, b''):
            #for line in out.readlines():
            line =  line.strip()
            write_fn(line)
    else:
        write_fn(out)

# Error
def result_error(err = ''):
    pass


def do_calculation(uri, output_dir):
    hashed_url = md5(uri).hexdigest()

    # Define path for each arguments of crawl.js
    crawljs_script = os.path.join(
        basedir, 'ext', 'phantomjs', 'crawl.js'
    )
    # Define damage-old.py location
    damage_py_script = os.path.join(
        basedir, 'ext', 'damage.py'
    )

    # Define arguments
    screenshot_file = os.path.join(output_dir, 'screenshot',
                                   '{}.png'.format(hashed_url))
    html_file = os.path.join(output_dir, 'html',
                                   '{}.html'.format(hashed_url))
    log_file = os.path.join(output_dir, 'log',
                                   '{}.log'.format(hashed_url))
    images_log_file = os.path.join(output_dir, 'log',
                                   '{}.img.log'.format(hashed_url))
    csses_log_file = os.path.join(output_dir, 'log',
                                   '{}.css.log'.format(hashed_url))
    crawler_log_file = os.path.join(output_dir, 'log',
                                   '{}.crawl.log'.format(hashed_url))
    damage_result_file = os.path.join(output_dir, 'result.csv')

    try:
        os.makedirs(os.path.join(output_dir, 'screenshot'))
        os.makedirs(os.path.join(output_dir, 'html'))
        os.makedirs(os.path.join(output_dir, 'log'))
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise

    print('Processing damage calculation of {}'.format(uri))
    print('To see progress, uncomment print in section [Verbose] or open {}'
          .format(os.path.abspath(crawler_log_file)))

    # page background-color will be set from phantomjs result
    page = {'background_color': 'FFFFFF'}

    # Define writer
    # Logger
    f = open(crawler_log_file, 'w')
    f.write('')
    f.close()

    f = open(crawler_log_file, 'a')

    def write(line):
        f.write(line + '\n')

        # [Verbose]
        # If you want verbose stdout, uncomment the line below
        print(line)

        if 'background_color' in line and page:
            line = json.loads(line)
            if line['background_color']:
                page['background_color'] = line['background_color']
        if 'result' in line:
            try:
                line = json.loads(line)

                result = line['result']
                result['error'] = False
                result['is_archive'] = False

                # Print total damage
                print('Total damage of {} is {}'.format(
                    uri, str(result['total_damage'])))

                # Write result to file
                with open(damage_result_file, 'a+') as res:
                    res.write(','.join((uri, str(result['total_damage']))) +
                              '\n')
            except (ValueError, KeyError) as e:
                pass

    # Crawl page with phantomjs crawl.js via arguments
    # Equivalent with console:
    cmd = Command(['phantomjs', '--ssl-protocol=any', crawljs_script,
                   uri, output_dir],
                  log_output)
    err_code = cmd.run(10 * 60, args=(write, ))

    if err_code == 0:
        python = sys.executable

        # Calculate damage with damage-old.py via arguments
        # Equivalent with console:
        #   python damage.py <uri> <cache_dir> <bg>
        cmd = Command([python, damage_py_script, uri, output_dir,
                       page['background_color']],
                      log_output)

        err_code = cmd.run(10 * 60, args=(write, ))
        if err_code != 0:
            result_error()
    else:
        result_error()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Usage :')
        print('python cli/damage.py <uri or csv> <output_dir>')
        exit()

    uri = sys.argv[1]
    output_dir = sys.argv[2]

    output_dir = os.path.abspath(output_dir)

    if os.path.isfile(uri):
        with open(uri) as f:
            for row in csv.reader(f):
                uri = row[0]
                do_calculation(uri, output_dir)
    else:
        do_calculation(uri, output_dir)
