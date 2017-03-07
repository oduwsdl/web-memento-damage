import errno
import json
import os
import tempfile
import urllib
import numpy as np
import requests
from datetime import datetime
from optparse import OptionParser
from bs4 import BeautifulSoup
from memento_damage import MementoDamage
from multiprocess import Queue, Process
# from matplotlib import pyplot as plt


def column(matrix, i):
    return [row[i] for row in matrix]


class MultiProcess(object):
    def __init__(self, cores=4):
        self.cores = cores

    def map(self, function, sequence):
        def _map(fn, list, q):
            q.put(map(fn, list))

        sl_idx = np.array_split(np.array(range(len(sequence))), self.cores)

        sublist = []
        for sli in sl_idx:
            sublist.append([sequence[i] for i in sli])

        arr_ps = []
        q = Queue()
        for sl in sublist:
            p = Process(target=_map, args=(function, sl, q,))
            p.daemon = True
            arr_ps.append(p)

        for p in arr_ps: p.start()

        results = []
        for _ in arr_ps:
            results += q.get()

        return results


class URIMCrawler(object):
    pool = MultiProcess(20)

    def get_uri_ms(self, index_uri, uri_r, idx, total):
        print '{0}/{1} Get URI-M for {3} from {4}'.format(idx, total, uri_r, index_uri)

        uri_ms = []
        try:
            resp_index = requests.get(index_uri)
            if resp_index.status_code == 200:
                resp_index_content = resp_index.content

                # Content is in link format, convert it so it looks like html format
                resp_index_content = resp_index_content.replace('<', '<a href="') \
                    .replace('>;', '"').replace('; ', ' ').replace('",', '" />') \
                    .replace('\n', '') + ' />'

                bs = BeautifulSoup(resp_index_content, 'html.parser')
                for memento in bs.findAll('a', rel="memento"):
                    uri_m = memento['href'].strip()
                    uri_m_time = datetime.strptime(memento['datetime'], '%a, %d %b %Y %H:%M:%S %Z')
                    uri_ms.append((uri_r, uri_m, str(uri_m_time.year), str(uri_m_time), ))
        except: pass

        return uri_ms

    def get_uri_ms_wrapper(self, args):
        if not (type(args) == list or type(args) == tuple):
            args = [args, ]

        return self.get_uri_ms(*args)

    def get_index_uris(self, uri_r, idx, total):
        print '{0}/{1} Get index uris for URI-R = {2}'.format(idx, total, uri_r)

        index_uris = []
        try:
            resp_timemap = requests.get('http://timetravel.mementoweb.org/timemap/json/{}'.format(uri_r))
            if resp_timemap.status_code == 200:
                resp_timemap_content = resp_timemap.json()
                index_uris = [(index['uri'], uri_r, idx, total) for index in resp_timemap_content['timemap_index']]
        except: pass

        print '{0}/{1} Index uris = {2} for URI-R = {3}'.format(idx, total, len(index_uris), uri_r)
        return index_uris

    def get_index_uris_wrapper(self, args):
        if not (type(args) == list or type(args) == tuple):
            args = [args, ]

        return self.get_index_uris(*args)

    def process_input(self, uri_r_file, uri_r_file_output):
        flat_uri_ms = []
        if not os.path.exists(uri_r_file_output):
            uri_rs = [u.strip() for u in open(uri_r_file).readlines()]
            uri_rs = [(u, i+1, len(uri_rs)) for i, u in enumerate(uri_rs)]

            index_uris = self.pool.map(self.get_index_uris_wrapper, uri_rs)

            # Combine into flat arrays
            flat_index_uris = []
            for iu in index_uris:
                flat_index_uris += iu

            uri_ms = self.pool.map(self.get_uri_ms_wrapper, flat_index_uris)

            # Combine into flat arrays
            for iu in uri_ms:
                flat_uri_ms += iu

            with open(uri_r_file_output, 'wb') as f:
                str_row = []
                for r in flat_uri_ms:
                    str_row.append(','.join(r))

                f.write('\n'.join(str_row))
        else:
            for l in open(uri_r_file_output).readlines():
                flat_uri_ms.append(l.strip().split(','))

        return flat_uri_ms


class URIMDamage(object):
    pool = MultiProcess(20)

    def process_uri_m(self, uri_r, uri_m, year, time, outdir):
        quoted_url = urllib.quote(uri_m).replace('/', '_').replace('.', '-')
        out_json_file = os.path.join(outdir, quoted_url + '.json')

        try: os.makedirs(outdir)
        except OSError, e:
            if e.errno != errno.EEXIST: raise

        print 'Processing {0}'.format(uri_m)

        result = None
        if not os.path.exists(out_json_file):
            m = MementoDamage(uri_m, tempfile.mkdtemp())
            m.set_show_debug_message()
            m.set_output_mode_json()
            # m.set_dont_clean_cache_on_finish()
            m.set_follow_redirection()

            m.run()

            result = m.get_result()
            with open(out_json_file, 'wb') as f:
                json.dump(result, f, indent=4)
        '''
        else:
            result = json.load(open(out_json_file))

        return uri_r, uri_m, year, time, result
        '''

        return uri_r, uri_m, year, time

    def process_uri_m_wrapper(self, args):
        if not (type(args) == list or type(args) == tuple):
            args = [args, ]

        return self.process_uri_m(*args)

    def process(self, uri_ms, outdir):
        p_uri_ms = [list(u) + [outdir, ] for u in uri_ms]
        return self.pool.map(self.process_uri_m_wrapper, p_uri_ms)


if __name__ == '__main__':
    parser = OptionParser()
    options, args = parser.parse_args()

    if len(args) != 3:
        print 'Parameter must be three.'
        print '<uri_r.txt> <out_uri_m.txt> <out_dir>'
        exit()

    uri_ms = URIMCrawler().process_input(args[0], args[1])
    uri_damages = URIMDamage().process(uri_ms, args[2])

'''
    # Make graph
    damages_per_year = {}
    missings_per_year = {}
    for uri_r, uri_m, year, time, damage in uri_damages:
        if not damage['error']:
            damages_per_year.setdefault(year, [])
            damages_per_year[year].append(damage['total_damage'])

            csses = damage['csses']
            jses = damage['jses']
            images = damage['images']
            multimedias = damage['multimedias']

            resources = csses + jses + images + multimedias
            missings = 0
            for res in resources:
                if 'status_code' in res and res['status_code'] > 399:
                    missings += 1

            missings_per_year[year] = float(missings) / len(resources)

    arr_damage_year = []
    for year, damages in damages_per_year.items():
        arr_damage_year.append((int(year), float(sum(damages)) / len(damages), missings_per_year[year]))

    arr_damage_year.sort()

    plt.plot(column(arr_damage_year, 0), column(arr_damage_year, 1), 'ro')
    plt.plot(column(arr_damage_year, 0), column(arr_damage_year, 1), '--')
    plt.plot(column(arr_damage_year, 0), column(arr_damage_year, 2), 'ro')
    plt.plot(column(arr_damage_year, 0), column(arr_damage_year, 2), '--')
    plt.show()
'''