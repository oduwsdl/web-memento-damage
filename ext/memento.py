import requests
from bs4 import BeautifulSoup


class MementoWebListener:
    def on_loaded(self):
        pass
    def on_received(self):
        pass

class MementoWeb:
    # Archive sites are taken from
    # http://ws-dl.blogspot.co.id/2016/04/2016-04-27-mementos-in-raw.html
    # Use agregator as be described in
    # http://timetravel.mementoweb.org/guide/api/
    agregator_url = 'http://timetravel.mementoweb.org/timemap/json/{}'

    def __init__(self, url):
        self.original_url = url
        self.agregator_url = self.agregator_url.format(self.original_url)

    def find(self, rel='memento', time=None):
        resp = requests.get(self.agregator_url)
        self.timemap = resp.json()

        # Timemap will be looked like
        # http://timetravel.mementoweb.org/timemap/json/http://www.cityofmoorhead.com/flood/

        mementos = []
        registries = self.timemap['timemap_index']
        for registry in registries:
            url = registry['uri']
            reg_resp = requests.get(url)
            if reg_resp.status_code == 200:
                reg_timemap = reg_resp.text
                for memento in reg_timemap.split('\n'):
                    if memento:
                        mementos.append(memento)

        print('{} mementos found'.format(len(mementos)))

        # Convert to xml-like entry
        for idx, memento in enumerate(mementos):
            memento = memento.replace('<', '<memento url="')
            memento = memento.replace('>', '"')
            memento = memento.replace(';', '')
            memento = memento.replace('rel', 'class')
            if memento.endswith(','):
                memento = memento[:-1]
            memento += ' />'
            mementos[idx] = memento

        # Parse with beautifulsoup
        urls = []
        soup = BeautifulSoup(unicode(''.join(mementos)), "html5lib")
        for m in soup.find_all('memento', {"class" : rel}):
            urls.append(m['url'])

        return urls



# m = MementoWeb('http://www.cs.odu.edu/')
# m.find()
