import unicodecsv as csv
import os
import sys
from ext.tools import Command


basedir = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
measure_memento_pl_script = os.path.join(basedir, 'measureMemento.pl')

def log_output(out, write_fn):
    if out and hasattr(out, 'readline'):
        for line in iter(out.readline, b''):
            line = line.strip()
            write_fn(line)
    else:
        write_fn(out)

def write(line):
    print(line)

def do_calculation(uri, output_dir):
    print('=' * 75)
    print('Calculating {}'.format(uri))
    print('=' * 75)

    cmd = Command(['perl', measure_memento_pl_script, uri], log_output)
    err_code = cmd.run(10 * 60, args=(write, ))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage :')
        print('python damage.py <uri or csv>')
        exit()

    uri = sys.argv[1]
    # output_dir = sys.argv[2]

    # output_dir = os.path.abspath(output_dir)
    output_dir = ''

    if os.path.isfile(uri):
        with open(uri) as f:
            for row in csv.reader(f):
                uri = row[0]
                do_calculation(uri, output_dir)
    else:
        do_calculation(uri, output_dir)