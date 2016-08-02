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
        # print(line)

        if 'background_color' in line and page:
            page['background_color'] = json.loads(line)\
                                       ['background_color']
        if 'result' in line:
            line = json.loads(line)
            try:
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
            except KeyError:
                pass

    # Crawl page with phantomjs crawl.js via arguments
    # Equivalent with console:
    #   phantomjs crawl.js <screenshot> <html> <log>
    cmd = Command(['phantomjs', '--ssl-protocol=any', crawljs_script,
                   uri, screenshot_file, html_file, log_file],
                  log_output)
    err_code = cmd.run(10 * 60, args=(write, ))

    if err_code == 0:
        # Calculate damage with damage-old.py via arguments
        # Equivalent with console:
        #   python damage-old.py <img_log> <css_log> <screenshot_log> <bg>
        python = sys.executable

        cmd = Command([python, damage_py_script, images_log_file,
                       csses_log_file, screenshot_file,
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
        print('python test/damage-old.py <uri or csv> <output_dir>')
        exit()

    uri = sys.argv[1]
    output_dir = sys.argv[2]

    if os.path.isfile(uri):
        with open(uri) as f:
            for row in csv.reader(f):
                uri = row[0]
                do_calculation(uri, output_dir)
    else:
        do_calculation(uri, output_dir)