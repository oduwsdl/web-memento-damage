import errno
import json
import os
from datetime import datetime
from functools import partial
from urlparse import urlparse

from PyQt4.QtCore import QObject, SIGNAL, QUrl, QVariant
from PyQt4.QtGui import QImage, QPainter
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings

from PIL import Image
from damage import SiteDamage

'''
Section 'Crawl' ==============================================================
'''

def variant_to_json(variant):
    if variant.type() == QVariant.Map:
        obj = {}
        for k,v in variant.toMap().items():
            obj[unicode(k)] = variant_to_json(v)
        return obj
    if variant.type() == QVariant.List:
        lst = []
        for v in variant.toList():
            lst.append(variant_to_json(v))
        return lst
    if variant.type() == QVariant.String:
        return str(variant.toString())
    if variant.type() == QVariant.Int:
        return int(variant.toString())
    if variant.type() == QVariant.Double:
        return float(variant.toString())
    if variant.type() == QVariant.Bool:
        return bool(variant.toBool())

    return unicode(variant.toString())

class CrawlNetwork(QNetworkAccessManager):
    contentTypeHeader = QNetworkRequest.ContentTypeHeader

    def __init__(self, web, logger):
        QNetworkAccessManager.__init__(self)
        QObject.connect(self, SIGNAL("finished(QNetworkReply *)"),
                        self.finished)
        self.web = web
        self.logger = logger

    def finished(self, response):
        url = unicode(response.request().url().toString())
        base_url = unicode(self.web.page().mainFrame().baseUrl().toString())

        blocked = False
        for bl in self.web.blacklists:
            in_bl = str(bl) in str(url)
            blocked = blocked or in_bl

        headers = {}
        for header in response.rawHeaderList():
            headers[unicode(header.data())] = response.rawHeader(header).data()

        url_domain = '{uri.scheme}://{uri.netloc}/'.format(uri=urlparse(url))
        base_url_domain = '{uri.scheme}://{uri.netloc}/'.format(
            uri=urlparse(base_url))

        resource = {
            'url' : url,
            'content_type' : unicode(response.header(
                self.contentTypeHeader).toString()),
            'headers' : headers,
            'status_code' : response.attribute(
                QNetworkRequest.HttpStatusCodeAttribute).toInt(),
            'is_local' : url_domain == base_url_domain,
            'is_blocked' : blocked
        }
        self.logger(resource)

class CrawlBrowser(QWebView):
    resources = []

    def __init__(self):
        QWebView.__init__(self)
        self.settings().setAttribute(QWebSettings.JavascriptEnabled, True)

    def get_resources(self, output_file=None):
        if output_file:
            with open(output_file, 'wb') as f:
                print 'saving resources log to', output_file
                f.write('\n'.join([json.dumps(stat) for stat in
                                   self.resources]))

        return self.resources

    def make_directory_recursive(self, file):
        dir = os.path.dirname(os.path.realpath(file))
        try:
            os.makedirs(dir)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise

    def take_screenshot(self, output_file):
        # set to webpage size
        self.page().setViewportSize(self.page().mainFrame().contentsSize())

        # render image
        image = QImage(self.page().viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        self.page().mainFrame().render(painter)
        painter.end()

        # create directory of file
        self.make_directory_recursive(output_file)

        # save image
        print 'saving screenshot to', output_file
        image.save(output_file)

    def get_html(self, output_file=None):
        html = self.page().mainFrame().toHtml()
        html = unicode(html).encode('utf-8')
        if output_file:
            # create directory of file
            self.make_directory_recursive(output_file)

            print 'saving html source to', output_file
            with open(output_file, 'wb') as f:
                f.write(html)

        return html
    
    def get_images(self, output_file=None):
        imgs = {}
        res_urls = [res['url'] for res in self.resources]
        document = self.page().mainFrame().documentElement()
        for img in document.findAll('img'):
            for idx, res_url in enumerate(res_urls):
                if res_url.endswith(str(img.attribute('src'))):
                    if res_url not in imgs:
                        imgs[res_url] = self.resources[idx]
                        imgs[res_url].setdefault('rectangles', [])

                    imgs[res_url]['rectangles'].append({
                        'left' : img.geometry().x(),
                        'top' : img.geometry().y(),
                        'width' : img.geometry().width(),
                        'height' : img.geometry().height()
                    })

        if output_file:
            # create directory of file
            self.make_directory_recursive(output_file)

            with open(output_file, 'wb') as f:
                print 'saving images log to', output_file
                f.write('\n'.join([json.dumps(img) for url, img in
                                   imgs.items()]))

        return imgs.values()

    def get_background_color(self):
        jsFn = """
        function getBackgroundColor() {
            return document.body.style.backgroundColor || 'FFFFFF'
        }
        """

        return self.page().mainFrame().evaluateJavaScript(jsFn)
    
    def get_stylesheets(self, output_file=None):
        jsFn = """
        function getNumElementsByClass(className) {
            var counter = 0;
            var elems = document.getElementsByTagName('*');
            for (var i = 0; i < elems.length; i++) {
                if((' ' + elems[i].className + ' ').indexOf(' ' + className + ' ') > -1) {
                    counter++;
                }
            }
            return counter;
        }

        function getNumElementByID(id) {
            var theThing = document.getElementById(id);
            if(theThing == null)
                return 0;
            return 1;
        }

        function getNumElementsByTagAndClass(tagName, className) {
            var counter = 0;
            var elems = document.getElementsByTagName(tagName);
            for (var i = 0; i < elems.length; i++) {
                if((' ' + elems[i].className + ' ').indexOf(' ' + className + ' ') > -1) {
                    counter++;
                }
            }
            return counter;
        }

        function getNumElementsByTag(tagName) {
            return document.getElementsByTagName(tagName).length;
        }

        function cssRules() {
            var styles = document.styleSheets;
            var allRules = {};
            for(var s=0; s<styles.length; s++) {
                var style = styles[s];
                var rules = [];
                var selectors = []

                if(style.cssRules) {
                    rules = style.cssRules;
                } else if(style.rules) {
                    rules = style.rules;
                }

                for(var i=0; i < rules.length; i++) {
                    selectors.push(rules[i].selectorText);
                }

                if(style.href != null)
                    allRules[style.href] = selectors;
                else allRules['[INTERNAL]'] = selectors;
            }

            var allRulesImportance = {}
            for(url in allRules) {
                var props = allRules[url];
                var importance = 0;
                for(var p=0; p<props.length; p++) {
                    var prop = props[p];

                    if(prop == undefined) {
                        continue;
                    } else if(prop.match(/^\..*/i)) {
                        importance += getNumElementsByClass(prop);
                    } else if(prop.match(/^#.*/i)) {
                        var theArr = prop.split('#');
                        var theArr2 = theArr[1].split(' ');
                        var theGuy = theArr2[0];
                        importance += getNumElementByID(theGuy);
                    } else if(prop.match(/.*#.*/i)) {
                        importance += getNumElementByID(prop);
                    } else if(prop.match(/[a-zA-Z]*\..*/g)) {
                        var theArr = prop.split('.');
                        importance += getNumElementsByTagAndClass(theArr[0], theArr[1]);
                    } else if(!(prop.match(/\./ig))) {
                        importance += getNumElementsByTag(prop);
                    } else {

                    }
                }

                allRulesImportance[url] = {
                    //'src' : url,
                    'rules_tag' : props,
                    'importance' : importance
                }

                if(url=='[INTERNAL]')
                    allRulesImportance[url]['url'] = url
            }

            return allRulesImportance;
        }

        cssRules();
        """

        res_urls = [res['url'] for res in self.resources]
        stylesheets_importance = self.page().mainFrame().evaluateJavaScript(jsFn)
        stylesheets_importance = variant_to_json(stylesheets_importance)

        if output_file:
            # create directory of file
            self.make_directory_recursive(output_file)

            with open(output_file, 'wb') as f:
                csses = []
                for url, css in stylesheets_importance.items():
                    if '[INTERNAL]' in url:
                        csses.append(css)

                    for idx, res_url in enumerate(res_urls):
                        if res_url.endswith(url):
                            css.update(self.resources[idx])
                            csses.append(css)

                    print 'saving stylesheets log to', output_file
                    f.write('\n'.join([json.dumps(css) for css in csses]))

        return stylesheets_importance.values()

class CrawlListener:
    def on_start(self, id, browser):
        pass
    def on_loaded(self, id, browser):
        pass
    def on_resource_received(self, log, id, *browser):
        pass
    def on_finished(self, sessions):
        pass

class Crawler(object):
    sessions = dict()
    browsers = dict()
    blacklists = []

    def __init__(self, app, listener=CrawlListener()):
        self.app = app
        self.listener = listener

    def set_blacklists(self, blacklists):
        self.blacklists = blacklists

    def add_blacklist(self, blacklist):
        self.blacklists.append(blacklist)

    def browser_started(self, id, sess_id):
        browser, url, status = self.browsers[id]
        self.listener.on_start(id, browser)

    def browser_loaded(self, id, sess_id, is_loaded):
        if is_loaded:
            browser, url, status = self.browsers[id]
            if not status:
                self.browsers[id] = (browser, url, True)
                self.listener.on_loaded(id, browser)

        if all([status for browser, url, status in self.browsers.values()]):
            print('Session {} finished'.format(sess_id))
            urls = [url for browser, url, status in self.browsers.values()]
            self.sessions[sess_id] = (sess_id, urls, True)

        if all([status for id, urls, status in self.sessions.values()]):
            print('All sessions finished')
            self.listener.on_finished(self.sessions.values())
            self.app.quit()

        if all([status for browser, url, status in self.browsers.values()]):
            try:
                self.start_session(self.sessions[sess_id+1])
            except:
                pass

    def browser_resources_received(self, browser_id, session_id, log):
        self.browsers[browser_id][0].resources.append(log)
        browser, url, status = self.browsers[browser_id]
        self.listener.on_resource_received(log, browser_id, browser)
        # if not log['is_blocked']:
        #     self.resources.append(log)

    def start_session(self, session):
        sess_id, urls, is_processed = session
        print('Session {} started'.format(sess_id))

        for id, url in enumerate(urls):
            browser = CrawlBrowser()
            browser.blacklists = self.blacklists
            browser.setPage(QWebPage())

            network_fn = partial(self.browser_resources_received, id, sess_id)
            browser.page().setNetworkAccessManager(
                CrawlNetwork(browser, network_fn))

            started_fn = partial(self.browser_started, id, sess_id)
            browser.loadStarted.connect(started_fn)

            loaded_fn = partial(self.browser_loaded, id, sess_id)
            browser.loadFinished.connect(loaded_fn)

            self.browsers[id] = (browser, url, False)

        for id, (browser, url, status) in self.browsers.items():
            browser.load(QUrl(url))

    def start(self, urls):
        if isinstance(urls, basestring) or isinstance(urls, unicode):
            urls = [urls,]

        urls = list(set(urls))

        sessions_urls = [urls[x:x+10] for x in xrange(0, len(urls), 10)]
        for id, session_urls in enumerate(sessions_urls):
            self.sessions[id] = (id, session_urls, False)

        print('Processing {} urls in {} sessions'.format(len(urls),
                                                         len(self.sessions)))

        self.start_session(self.sessions[0])


if __name__ == "__main__":
    import sys
    import os
    from hashlib import md5
    from PyQt4.QtGui import QApplication

    if len(sys.argv) > 0:
        if len(sys.argv) != 3:
            print('Usage :')
            print('python crawl.py <url> <output_dir>')
            exit()

        url = sys.argv[1]
        output_dir = sys.argv[2]
        output_dir = os.path.abspath(output_dir)

        class CustomCrawlListener(CrawlListener):
            def on_start(self, id, browser):
                print('Browser {} is starting crawl {}\n\n'
                    .format(id, browser.page().mainFrame().requestedUrl()))
                self.timestart = datetime.now()

            def on_loaded(self, id, browser):
                url = str(browser.page().mainFrame().requestedUrl().toString())
                hashed_url = md5(url).hexdigest()

                browser.get_html('{}.html'.format(
                    os.path.join(output_dir, 'html', hashed_url)))
                browser.take_screenshot('{}.png'.format(
                    os.path.join(output_dir, 'screenshot', hashed_url)))
                images_log = browser.get_images('{}.img.log'.format(
                    os.path.join(output_dir, 'log', hashed_url)))
                csses_log = browser.get_stylesheets('{}.css.log'.format(
                    os.path.join(output_dir, 'log', hashed_url)))
                browser.get_resources('{}.log'.format(
                    os.path.join(output_dir, 'log', hashed_url)))

                print('Browser {} is finished crawl {}\n\n'
                             .format(id, url))

                print('Calculating site damage...')

                damage = SiteDamage(images_log, csses_log, '{}.png'.format(
                    os.path.join(output_dir, 'screenshot', hashed_url)),
                                    browser.get_background_color())

                potential_damage = damage.calculate_potential_damage()
                print('Potential Damage : {}'.format(potential_damage))

                actual_damage = damage.calculate_actual_damage()
                print('Actual Damage : {}'.format(actual_damage))

            def on_resource_received(self, log, id, *browser):
                print('Browser {} receive resource {}\n\n'
                             .format(id, log['url']))

            def on_finished(self, sessions):
                self.timefinish = datetime.now()
                process_time = (self.timefinish -
                                self.timestart).microseconds / 1000

                urls = [len(urls) for id, urls, status in sessions]

                print('All Finished\n\n')
                print('{} URIs has crawled in {} sessions in {} '
                      'seconds\n\n'.format(sum(urls), len(urls),
                                               process_time))

        app = QApplication([])
        crawler = Crawler(app, CustomCrawlListener())
        crawler.add_blacklist('http://web.archive.org/static')
        crawler.start(url)

        app.exec_()

