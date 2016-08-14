import unicodecsv as csv
import os
import sys
from ext.tools import Command


basedir = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
measure_memento_pl_script = os.path.join(basedir, 'measureMemento.pl')
measure_memento_result_file = os.path.join(basedir, 'testing', 'result.csv')

def log_output(out, uri, write_fn):
    if out and hasattr(out, 'readline'):
        for line in iter(out.readline, b''):
            line = line.strip()
            write_fn(uri, line)
    else:
        write_fn(uri, out)

def write(uri, line):
    print(line)

    # Write result to file
    if 'TOTAL, ' in line:
        # Example: TOTAL, 0.153896757560811
        results = line.split(',')
        damage = float(results[1])

        with open(measure_memento_result_file, 'a+') as res:
            res.write(','.join((uri, str(damage))) + '\n')

def do_calculation(uri, output_dir):
    print('=' * 75)
    print('Calculating {}'.format(uri))
    print('=' * 75)

    cmd = Command(['perl', measure_memento_pl_script, uri], log_output)
    err_code = cmd.run(10 * 60, args=(uri, write, ))

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