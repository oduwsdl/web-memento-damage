import io
import json
import math
import os
import urllib
import urlparse
import httplib
from collections import namedtuple

import html2text
import sys

import itertools
from PIL import Image

from memento_damage.tools import rectangle_intersection_area


Rectangle = namedtuple('Rectangle', 'xmin ymin xmax ymax')

class MementoDamageAnalysis(object):
    image_importance = {}
    css_importance = 0

    page_size = [1024, 768]  # Default size
    viewport_size = [1024, 768]  # Default size

    multimedia_weight = 0.50
    css_weight = 0.05
    js_weight = 0.05
    proportion = 3.0 / 4.0
    image_weight = proportion * (1 - (multimedia_weight + css_weight + js_weight))
    text_weight = 1.0 - (multimedia_weight + css_weight + js_weight + image_weight)
    words_per_image = 1000
    iframe_weight = image_weight

    blacklisted_uris = [
        'https://analytics.archive.org/',
        'http://analytics.archive.org/',
        'https://web.archive.org/static',
        'http://web.archive.org/static',
        '[INTERNAL]',
        'data:',
    ]

    def __init__(self, memento_damage):
        self.memento_damage = memento_damage

        # Read log contents
        h = html2text.HTML2Text()
        h.ignore_links = True
        self._text = h.handle(
            u' '.join([line.strip() for line in io.open(memento_damage.html_file, encoding="utf-8").readlines()]))

        logs = [json.loads(log, strict=False) for log in
                io.open(memento_damage.network_log_file, encoding="utf-8").readlines()]
        for i in range(len(logs)):
            logs[i]['url'] = urllib.unquote(logs[i]['url'])
        self._network_logs = {urllib.unquote(log['url'].lower()): log for log in logs}

        self._image_logs = [json.loads(log, strict=False) for log in
                            io.open(memento_damage.image_log_file, encoding="utf-8").readlines()]
        self._css_logs = [json.loads(log, strict=False) for log in
                          io.open(memento_damage.css_log_file, encoding="utf-8").readlines()]
        self._js_logs = [json.loads(log, strict=False) for log in
                         io.open(memento_damage.js_log_file, encoding="utf-8").readlines()]
        self._mlm_logs = [json.loads(log, strict=False) for log in
                          io.open(memento_damage.video_log_file, encoding="utf-8").readlines()]
        self._text_logs = [json.loads(log, strict=False) for log in
                           io.open(memento_damage.text_log_file, encoding="utf-8").readlines()]
        self._iframe_logs = [json.loads(log, strict=False) for log in
                             io.open(memento_damage.iframe_log_file, encoding="utf-8").readlines()]
        self.redirection_mapping = {}
        # self._text_logs = {}

        self.viewport_size = self.memento_damage.viewport_size
        im = Image.open(self.memento_damage.screenshot_file)
        self.page_size = im.size

        self._logger = self.memento_damage.logger

    def run(self):
        self.detect_redirection()
        self.remove_blacklisted_uris()
        self.remove_hidden_elements()
        self.resolve_redirection()
        self.calculate_percentage_coverage()

        self._logger.info('Start calculating damage...')

        self.calculate_image_damage()
        self.calculate_multimedia_damage()
        self.calculate_css_damage()
        self.calculate_javascript_damage()
        self.calculate_text_damage()
        self.calculate_iframe_damage()
        self.calculate_damage()

        # self._calculate_potential_damage()
        # self._calculate_actual_damage()

        self._logger.info('Done calculating damage')

    def detect_redirection(self):
        reverse_redirection_mapping = {}
        for url, log in self._network_logs.items():
            if log['status_code'] in [301, 302, 307, 308] and 'headers' in log and 'Location' in log['headers']:
                redirect_url = urlparse.urljoin(url.lower(), log['headers']['Location'].lower())
                # print('url.lower adalah = {}'.format(url.lower()))
                # print('headers location adalah = {}'.format(log['headers']['Location'].lower()))
                # print('redirect_url adalah = {}'.format(redirect_url))
                self.redirection_mapping[urllib.unquote(url.lower())] = urllib.unquote(redirect_url)
                reverse_redirection_mapping[urllib.unquote(redirect_url)] = urllib.unquote(url.lower())

        # print('redirection mapping adalah = {}'.format(self.redirection_mapping))
        # print('reverse_redirection_mapping adalah = {}'.format(reverse_redirection_mapping))
        self.redirect_urls = self._detect_redirection({'url': self.memento_damage.uri}, self.redirection_mapping)
        # print('redirect_urls detect_redirection adalah = {}'.format(self.redirect_urls))
        # print("log redirect adalah = {}".format({'url': self.memento_damage.uri}))

        # print('enumerate image logs adalah = {}'.format(enumerate(self._image_logs)))

        for idx, log in enumerate(self._image_logs):
            redirect_urls = self._detect_redirection(log, self.redirection_mapping)
            self._image_logs[idx]['redirect_urls'] = redirect_urls
            # print('redirect_urls image adalah = {}'.format(redirect_urls))

        for idx, log in enumerate(self._css_logs):
            redirect_urls = self._detect_redirection(log, self.redirection_mapping)
            self._css_logs[idx]['redirect_urls'] = redirect_urls
            # print('redirect_urls css adalah = {}'.format(redirect_urls))

        for idx, log in enumerate(self._js_logs):
            redirect_urls = self._detect_redirection(log, self.redirection_mapping)
            self._js_logs[idx]['redirect_urls'] = redirect_urls
            # print('redirect_urls js adalah = {}'.format(redirect_urls))

        for idx, log in enumerate(self._mlm_logs):
            redirect_urls = self._detect_redirection(log, self.redirection_mapping)
            self._mlm_logs[idx]['redirect_urls'] = redirect_urls
            # print('redirect_urls mlm_logs adalah = {}'.format(redirect_urls))

        for idx, log in enumerate(self._text_logs):
            redirect_urls = self._detect_redirection(log, self.redirection_mapping)
            self._text_logs[idx]['redirect_urls'] = redirect_urls
            # print('redirect_urls text adalah = {}'.format(redirect_urls))

        for idx, log in enumerate(self._iframe_logs):
            redirect_urls = self._detect_redirection(log, self.redirection_mapping)
            self._iframe_logs[idx]['redirect_urls'] = redirect_urls
            # print('redirect_urls iframe adalah = {}'.format(redirect_urls))

    def _detect_redirection(self, log, redirection_mapping):
        redirect_urls = []

        if 'url' in log:
            t_url = log['url'].lower()
            t_url = urllib.unquote(t_url)
            while True:
                a = zip(*redirect_urls)
                print('a = {} with len = {}'.format(a, len(a)))
                if len(a) > 0 and t_url in a[0]:
                    break

                if t_url in self._network_logs:
                    redirect_urls.append((t_url, self._network_logs[t_url]['status_code'],
                                          self._network_logs[t_url]['content_type']))

                if t_url in redirection_mapping:
                    t_url = redirection_mapping[t_url]
                else:
                    break

        # print('redirect_urls _detect_redireg adalah = {}'.format(redirect_urls))
        return redirect_urls

    def remove_blacklisted_uris(self):
        to_be_removed = []
        for idx, log in enumerate(self._image_logs):
            if 'url' in log and self._is_blacklisted(log):
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._image_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._css_logs):
            if 'url' in log and self._is_blacklisted(log):
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._css_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._js_logs):
            if 'url' in log and self._is_blacklisted(log):
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._js_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._mlm_logs):
            if 'url' in log and self._is_blacklisted(log):
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._mlm_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._text_logs):
            if 'url' in log and self._is_blacklisted(log):
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._text_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._iframe_logs):
            if 'url' in log and self._is_blacklisted(log):
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._iframe_logs.pop(idx)

    def remove_hidden_elements(self):
        to_be_removed = []
        for idx, log in enumerate(self._image_logs):
            if 'visible' in log and not log['visible']:
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._image_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._css_logs):
            if 'visible' in log and not log['visible']:
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._css_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._js_logs):
            if 'visible' in log and not log['visible']:
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._js_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._mlm_logs):
            if 'visible' in log and not log['visible']:
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._mlm_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._text_logs):
            if 'visible' in log and not log['visible']:
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._text_logs.pop(idx)

        to_be_removed = []
        for idx, log in enumerate(self._iframe_logs):
            if 'visible' in log and not log['visible']:
                to_be_removed.append(idx)
        for idx in sorted(to_be_removed, reverse=True):
            self._iframe_logs.pop(idx)

    def resolve_redirection(self):
        for idx, log in enumerate(self._image_logs):
            if 'url' in log and len(log['redirect_urls']) > 0:
                final_url, final_status, content_type = log['redirect_urls'][len(log['redirect_urls']) - 1]
                self._image_logs[idx]['url'] = final_url
                self._image_logs[idx]['status_code'] = final_status
                self._image_logs[idx]['content_type'] = content_type

        for idx, log in enumerate(self._css_logs):
            if 'url' in log and len(log['redirect_urls']) > 0:
                final_url, final_status, content_type = log['redirect_urls'][len(log['redirect_urls']) - 1]
                self._css_logs[idx]['url'] = final_url
                self._css_logs[idx]['status_code'] = final_status
                self._css_logs[idx]['content_type'] = content_type

        for idx, log in enumerate(self._js_logs):
            if 'url' in log and len(log['redirect_urls']) > 0:
                final_url, final_status, content_type = log['redirect_urls'][len(log['redirect_urls']) - 1]
                self._js_logs[idx]['url'] = final_url
                self._js_logs[idx]['status_code'] = final_status
                self._js_logs[idx]['content_type'] = content_type

        for idx, log in enumerate(self._mlm_logs):
            if 'url' in log and len(log['redirect_urls']) > 0:
                final_url, final_status, content_type = log['redirect_urls'][len(log['redirect_urls']) - 1]
                self._mlm_logs[idx]['url'] = final_url
                self._mlm_logs[idx]['status_code'] = final_status
                self._mlm_logs[idx]['content_type'] = content_type

        for idx, log in enumerate(self._text_logs):
            if 'url' in log and len(log['redirect_urls']) > 0:
                final_url, final_status, content_type = log['redirect_urls'][len(log['redirect_urls']) - 1]
                self._text_logs[idx]['url'] = final_url
                self._text_logs[idx]['status_code'] = final_status
                self._text_logs[idx]['content_type'] = content_type

        for idx, log in enumerate(self._iframe_logs):
            if 'url' in log and len(log['redirect_urls']) > 0:
                final_url, final_status, content_type = log['redirect_urls'][len(log['redirect_urls']) - 1]
                self._iframe_logs[idx]['url'] = final_url
                self._iframe_logs[idx]['status_code'] = final_status
                self._iframe_logs[idx]['content_type'] = content_type

    def get_result(self):
        if len(self.redirect_urls) > 0:
            final_uri, final_status_code, content_type = self.redirect_urls[len(self.redirect_urls) - 1]
        else:
            final_uri, final_status_code = self.memento_damage.uri, 200

        # if (not final_status_code) or (final_status_code == 404):
        #     total_damage = 1
        # elif self._potential_damage != 0:
        #     total_damage = self._actual_damage / self._potential_damage
        # else:
        #     total_damage = 0

        result = {}
        if final_status_code == 200:
            if self._potential_damage != 0:
                total_damage = self._actual_damage / self._potential_damage
            else:
                total_damage = 0

            result['uri'] = self.memento_damage.uri
            result['weight'] = {
                'multimedia': self.multimedia_weight,
                'css': self.css_weight,
                'js': self.js_weight,
                'image': self.image_weight,
                'text': self.text_weight,
                'iframe': self.iframe_weight,
            }
            result['images'] = self._image_logs
            result['csses'] = self._css_logs
            result['jses'] = self._js_logs
            result['multimedias'] = self._mlm_logs
            result['text'] = self._text_logs
            result['iframes'] = self._iframe_logs
            result['potential_damage'] = {
                'total': self._potential_damage,
                'image': self._potential_image_damage,
                'css': self._potential_css_damage,
                'js': self._potential_js_damage,
                'multimedia': self._potential_multimedia_damage,
                'text': self._potential_text_damage,
                'iframe': self._potential_iframe_damage,
            }
            result['actual_damage'] = {
                'total': self._actual_damage,
                'image': self._actual_image_damage,
                'css': self._actual_css_damage,
                'js': self._actual_js_damage,
                'multimedia': self._actual_multimedia_damage,
                'text': self._actual_text_damage,
                'iframe': self._actual_iframe_damage,
            }
            result['total_damage'] = total_damage
            result['redirect_uris'] = self.redirect_urls
            result['error'] = False
            result['is_archive'] = False

            self._logger.info('Calculate total damage (actual damage / potential damage) = {}'.format(total_damage))

        else:
            result['uri'] = self.memento_damage.uri
            result['error'] = True
            result['message'] = 'Error in loading url. Page {0} (Status code {1})' \
                .format(httplib.responses[final_status_code], final_status_code)

        return result

    def get_result_as_string(self):
        return json.dumps(self.get_result(), indent=4)

    def _is_blacklisted(self, log):
        is_blacklisted = False

        # Check whether uri is defined in blacklisted_uris
        for b_uri in self.blacklisted_uris:
            if 'url' in log and log['url'].startswith(b_uri):
                is_blacklisted = True
                break

        # If not defined, check whether uri has header 'Link' containing
        # <http://mementoweb.org/terms/donotnegotiate>; rel="type"
        if 'url' in log and log['url'] in self._network_logs:
            log = self._network_logs[log['url']]
            if 'headers' in log and 'Link' in log['headers'] and not is_blacklisted:
                if log['headers']['Link'] == '<http://mementoweb.org/terms/' \
                                             'donotnegotiate>; rel="type"':
                    is_blacklisted = True

        return is_blacklisted

    def calculate_percentage_coverage(self):
        im = Image.open(self.memento_damage.screenshot_file)

        '''
        ==================================================================
        # Coverage of images
        ==================================================================
        '''
        # Make flatmap of image logs
        flat_image_logs = []
        for idx, log in enumerate(self._image_logs):
            for r_idx, rect in enumerate(log['rectangles']):
                rect.update({'url': log['url']})
                flat_image_logs.append(rect)

        for a, b in itertools.combinations(range(len(flat_image_logs)), 2):
            # Detect image intersection
            x1 = flat_image_logs[a]['left']
            y1 = flat_image_logs[a]['top']
            w1 = flat_image_logs[a]['width']
            h1 = flat_image_logs[a]['height']
            ra = Rectangle(x1, y1, x1 + w1, y1 + h1)

            x2 = flat_image_logs[b]['left']
            y2 = flat_image_logs[b]['top']
            w2 = flat_image_logs[b]['width']
            h2 = flat_image_logs[b]['height']
            rb = Rectangle(x2, y2, x2 + w2, y2 + h2)

            area = rectangle_intersection_area(ra, rb)
            if area:
                flat_image_logs[b]['coverage'] = float(w2) * h2 - area
                if flat_image_logs[b]['coverage'] < area:
                    flat_image_logs[b]['important'] = False

        # Group flatmap of image logs by url
        image_coverages = {}
        for idx, log in enumerate(flat_image_logs):
            image_coverages.setdefault(log['url'], 0)
            if 'coverage' in log:
                image_coverages[log['url']] += log['coverage']
            else:
                image_coverages[log['url']] += float(log['width']) * log['height']

        for idx, log in enumerate(self._image_logs):
            viewport_w, viewport_h = log['viewport_size']
            if float(viewport_w * viewport_h) <= 0:
                # If javascript cannot calculate viewport size, use screenshot size,
                # since, it is representation of webpage
                viewport_w, viewport_h = im.size

            self._image_logs[idx]['percentage_coverage'] = float(image_coverages[log['url']]) / \
                                                           float(viewport_w * viewport_h)

        '''
        ==================================================================
        # Coverage of videos
        ==================================================================
        '''
        # Make flatmap of image logs
        flat_mlm_logs = []
        for idx, log in enumerate(self._mlm_logs):
            for r_idx, rect in enumerate(log['rectangles']):
                rect.update({'url': log['url']})
                flat_mlm_logs.append(rect)

        for a, b in itertools.combinations(range(len(flat_mlm_logs)), 2):
            # Detect image intersection
            x1 = flat_mlm_logs[a]['left']
            y1 = flat_mlm_logs[a]['top']
            w1 = flat_mlm_logs[a]['width']
            h1 = flat_mlm_logs[a]['height']
            ra = Rectangle(x1, y1, x1 + w1, y1 + h1)

            x2 = flat_mlm_logs[b]['left']
            y2 = flat_mlm_logs[b]['top']
            w2 = flat_mlm_logs[b]['width']
            h2 = flat_mlm_logs[b]['height']
            rb = Rectangle(x2, y2, x2 + w2, y2 + h2)

            area = rectangle_intersection_area(ra, rb)
            if area:
                flat_mlm_logs[b]['coverage'] = float(w2) * h2 - area
                if flat_mlm_logs[b]['coverage'] < area:
                    flat_mlm_logs[b]['important'] = False

        # Group flatmap of image logs by url
        image_coverages = {}
        for idx, log in enumerate(flat_mlm_logs):
            image_coverages.setdefault(log['url'], 0)
            if 'coverage' in log:
                image_coverages[log['url']] += log['coverage']
            else:
                image_coverages[log['url']] += float(log['width']) * log['height']

        for idx, log in enumerate(self._mlm_logs):
            viewport_w, viewport_h = log['viewport_size']
            if float(viewport_w * viewport_h) <= 0:
                # If javascript cannot calculate viewport size, use screenshot size,
                # since, it is representation of webpage
                viewport_w, viewport_h = im.size

            self._mlm_logs[idx]['percentage_coverage'] = float(image_coverages[log['url']]) / \
                                                           float(viewport_w * viewport_h)

        '''
        ==================================================================
        # Coverage of iframes
        ==================================================================
        '''
        for a, b in itertools.combinations(range(len(self._iframe_logs)), 2):
            # Detect iframe intersection
            x1 = self._iframe_logs[a]['left']
            y1 = self._iframe_logs[a]['top']
            w1 = self._iframe_logs[a]['width']
            h1 = self._iframe_logs[a]['height']
            ra = Rectangle(x1, y1, x1 + w1, y1 + h1)

            x2 = self._iframe_logs[b]['left']
            y2 = self._iframe_logs[b]['top']
            w2 = self._iframe_logs[b]['width']
            h2 = self._iframe_logs[b]['height']
            rb = Rectangle(x2, y2, x2 + w2, y2 + h2)

            area = rectangle_intersection_area(ra, rb)
            if area:
                if self._iframe_logs[a]['parent'] or self._iframe_logs[b]['parent']:
                    uri_a_reds = self._detect_redirection({'url': self._iframe_logs[a]['url']},
                                                          self.redirection_mapping)
                    uri_b_reds = self._detect_redirection({'url': self._iframe_logs[b]['url']},
                                                          self.redirection_mapping)
                    uri_pa_reds = self._detect_redirection({'url': self._iframe_logs[a]['parent']},
                                                           self.redirection_mapping)
                    uri_pb_reds = self._detect_redirection({'url': self._iframe_logs[b]['parent']},
                                                           self.redirection_mapping)

                    fa = uri_a_reds[len(uri_a_reds) - 1][0] if len(uri_a_reds) > 0 else None
                    fb = uri_b_reds[len(uri_b_reds) - 1][0] if len(uri_b_reds) > 0 else None
                    fpa = uri_pa_reds[len(uri_pa_reds) - 1][0] if len(uri_pa_reds) > 0 else None
                    fpb = uri_pb_reds[len(uri_pb_reds) - 1][0] if len(uri_pb_reds) > 0 else None

                    if fpa and fb and fpa.lower() == fb.lower():
                        self._iframe_logs[b]['coverage'] = float(w2) * h2 - area
                        if self._iframe_logs[b]['coverage'] < area:
                            self._iframe_logs[b]['important'] = False
                    elif fpb and fa and fpb.lower() == fa.lower():
                        self._iframe_logs[a]['coverage'] = float(w1) * h1 - area
                        if self._iframe_logs[a]['coverage'] < area:
                            self._iframe_logs[a]['important'] = False
                else:
                    self._iframe_logs[b]['coverage'] = float(w2) * h2 - (float(w1 * h1))
                    if self._iframe_logs[b]['coverage'] < area:
                        self._iframe_logs[b]['important'] = False

            if 'important' not in self._iframe_logs[a]: self._iframe_logs[a]['important'] = True
            if 'important' not in self._iframe_logs[b]: self._iframe_logs[b]['important'] = True

        for idx, log in enumerate(self._iframe_logs):
            viewport_w, viewport_h = log['viewport_size']
            w, h = log['width'], log['height']
            coverage = float(w) * h
            if 'coverage' in log:
                coverage = log['coverage']
            self._iframe_logs[idx]['percentage_coverage'] = coverage / (float(viewport_w) * viewport_h)

        self._logger.info('Calculate percentage coverage')

    def calculate_image_damage(self):
        self._logger.info('Calculating damage for Image(s)')

        total_potential_damage = 0.0
        total_actual_damage = 0.0

        for idx, log in enumerate(self._image_logs):
            image_damage = self._calculate_image_and_multimedia_damage(log, use_viewport_size=True)

            # Potential
            # Based on measureMemento.pl line 463
            total_location_importance = 0.0
            total_size_importance = 0.0
            total_importance = 0.0
            for location_importance, size_importance, importance in image_damage:
                total_location_importance += location_importance
                total_size_importance += size_importance
                total_importance += importance

            total_potential_damage += total_importance

            self._image_logs[idx]['potential_damage'] = {
                'location': total_location_importance,
                'size': total_size_importance,
                'total': total_importance
            }

            self._logger.info('Potential damage of {} is {}'.format(log['url'], total_importance))

            # Actual
            if 'url' in log and log['url'] in self._network_logs and 'status_code' in self._network_logs[log['url']] \
                    and self._network_logs[log['url']]['status_code'] > 399:
                total_actual_damage += total_importance

                self._image_logs[idx]['actual_damage'] = {
                    'location': total_location_importance,
                    'size': total_size_importance,
                    'total': total_importance
                }

                self._logger.info('Actual damage of {} is {}'.format(log['url'], total_importance))

        self._potential_image_damage = total_potential_damage * self.image_weight
        self._actual_image_damage = total_actual_damage * self.image_weight

        self._logger.info('Calculating damage for Image(s) is Done')

    def calculate_multimedia_damage(self):
        self._logger.info('Calculating damage for Multimedia(s)')

        total_potential_damage = 0.0
        total_actual_damage = 0.0

        for idx, log in enumerate(self._mlm_logs):
            image_damage = self._calculate_image_and_multimedia_damage(log, use_viewport_size=True)

            # Potential
            # Based on measureMemento.pl line 463
            total_location_importance = 0.0
            total_size_importance = 0.0
            total_importance = 0.0
            for location_importance, size_importance, importance in image_damage:
                total_location_importance += location_importance
                total_size_importance += size_importance
                total_importance += importance

            total_potential_damage += total_importance

            self._mlm_logs[idx]['potential_damage'] = {
                'location': total_location_importance,
                'size': total_size_importance,
                'total': total_importance
            }

            self._logger.info('Potential damage of {} is {}'.format(log['url'], total_importance))

            # Actual
            if 'url' in log and log['url'] in self._network_logs and 'status_code' in self._network_logs[log['url']] \
                    and self._network_logs[log['url']]['status_code'] > 399:
                total_actual_damage += total_importance

                self._mlm_logs[idx]['actual_damage'] = {
                    'location': total_location_importance,
                    'size': total_size_importance,
                    'total': total_importance
                }

                self._logger.info('Actual damage of {} is {}'.format(log['url'], total_importance))

        self._potential_multimedia_damage = total_potential_damage * self.multimedia_weight
        self._actual_multimedia_damage = total_actual_damage * self.multimedia_weight

        self._logger.info('Calculating damage for Multimedia(s) is Done')

    def calculate_css_damage(self):
        self._logger.info('Calculating damage for Stylesheet(s)')

        total_potential_damage = 0.0
        total_actual_damage = 0.0

        for idx, log in enumerate(self._css_logs):
            tag_importance, ratio_importance, total_importance = self._calculate_css_damage(log, is_potential=True,
                                                                                            use_viewport_size=True)

            # Based on measureMemento.pl line 468
            total_potential_damage += total_importance

            self._css_logs[idx]['potential_damage'] = {
                'tag': tag_importance,
                'ratio': ratio_importance,
                'total': total_importance
            }

            self._logger.info('Potential damage of {} is {}'.format(log['url'], total_importance))

            if 'url' in log and log['url'] in self._network_logs and 'status_code' in self._network_logs[log['url']] \
                    and self._network_logs[log['url']]['status_code'] > 399:
                tag_importance, ratio_importance, total_importance = self._calculate_css_damage(log, is_potential=False,
                                                                                                use_viewport_size=False)

                # Based on measureMemento.pl line 468
                total_actual_damage += total_importance

                self._css_logs[idx]['actual_damage'] = {
                    'tag': tag_importance,
                    'ratio': ratio_importance,
                    'total': total_importance
                }

                self._logger.info('Actual damage of {} is {}'.format(log['url'], total_importance))

        self._potential_css_damage = total_potential_damage * self.css_weight
        self._actual_css_damage = total_actual_damage * self.css_weight

        self._logger.info('Calculating damage for Stylesheet(s) is Done')

    def calculate_javascript_damage(self):
        self._logger.info('Calculating damage for Javascript(s)')

        total_potential_damage = 0.0
        total_actual_damage = 0.0

        for idx, log in enumerate(self._js_logs):
            total_potential_damage += 1

            self._js_logs[idx]['potential_damage'] = {
                'total': 1
            }

            self._logger.info('Potential damage of {} is {}'.format(log['url'], 1))

            if 'url' in log and log['url'] in self._network_logs and 'status_code' in self._network_logs[log['url']] \
                    and self._network_logs[log['url']]['status_code'] > 399:
                total_actual_damage += 1

                self._js_logs[idx]['actual_damage'] = {
                    'total': 1
                }

                self._logger.info('Actual damage of {} is {}'.format(log['url'], 1))

        self._potential_js_damage = total_potential_damage * self.js_weight
        self._actual_js_damage = total_actual_damage * self.js_weight

        self._logger.info('Calculating damage for Javascript(s) is Done')

    def calculate_text_damage(self):
        self._logger.info('Calculating damage for Text(s)')

        num_words = len(self._text.split())
        total_potential_damage = float(num_words) / self.words_per_image
        total_actual_damage = 0.0

        self._text_logs = {}
        self._text_logs['num_words'] = num_words
        self._text_logs['words_per_image'] = self.words_per_image

        # total_potential_damage = 0.0
        # total_actual_damage = 0.0
        # num_words = 0
        #
        # for idx, log in enumerate(self._text_logs):
        #     if len(log['text']) > 0:
        #         text_damages = self._calculate_text_damage(log, use_viewport_size=True)
        #         # Based on measureMemento.pl line 463
        #         total_location_importance = 0
        #         total_size_importance = 0
        #         total_importance = 0
        #         for location_importance, size_importance, importance in text_damages:
        #             total_location_importance += location_importance
        #             total_size_importance += size_importance
        #             total_importance += importance
        #
        #         total_potential_damage += total_importance
        #         num_words += len(log['text'])
        #
        #         self._text_logs[idx]['potential_damage'] = {
        #             'location': total_location_importance,
        #             'size': total_size_importance,
        #             'total': total_importance
        #         }
        #     else:
        #         try:
        #             self._text_logs.pop(idx)
        #         except:
        #             pass

        self._potential_text_damage = total_potential_damage * self.text_weight
        self._actual_text_damage = total_actual_damage * self.text_weight

        self._logger.info('Potential damage of {} is {}'.format('"text"', self._potential_text_damage))
        self._logger.info('Actual damage of {} is {}'.format('"text"', self._actual_text_damage))

        self._logger.info('Calculating damage for Text(s) is Done')

    def calculate_iframe_damage(self):
        self._logger.info('Calculating damage for IFrame(s)')

        total_potential_damage = 0.0
        total_actual_damage = 0.0

        for idx, log in enumerate(self._iframe_logs):
            damage = self._calculate_iframe_damage(log, use_viewport_size=True)

            # Potential
            # Based on measureMemento.pl line 463
            total_location_importance = 0.0
            total_size_importance = 0.0
            total_importance = 0.0
            for location_importance, size_importance, importance in damage:
                total_location_importance += location_importance
                total_size_importance += size_importance
                total_importance += importance

            total_potential_damage += total_importance

            self._iframe_logs[idx]['potential_damage'] = {
                'location': total_location_importance,
                'size': total_size_importance,
                'total': total_importance
            }

            self._logger.info('Potential damage of {} is {}'.format(log['url'], total_importance))

            # Actual
            if 'url' in log and log['url'] in self._network_logs and 'status_code' in self._network_logs[log['url']] \
                    and self._network_logs[log['url']]['status_code'] > 399:
                total_actual_damage += total_importance

                self._iframe_logs[idx]['actual_damage'] = {
                    'location': total_location_importance,
                    'size': total_size_importance,
                    'total': total_importance
                }

                self._logger.info('Actual damage of {} is {}'.format(log['url'], total_importance))

        self._potential_iframe_damage = total_potential_damage * self.iframe_weight
        self._actual_iframe_damage = total_actual_damage * self.iframe_weight

        self._logger.info('Calculating damage for IFrame(s) is Done')

    def calculate_damage(self):
        self._logger.info('Calculating damage for "webpage"')

        self._potential_damage = self._potential_image_damage + \
                                 self._potential_css_damage + \
                                 self._potential_js_damage + \
                                 self._potential_multimedia_damage + \
                                 self._potential_text_damage + \
                                 self._potential_iframe_damage

        self._logger.info('Potential damage of {} is {}'.format('"webpage"', self._potential_damage))

        self._actual_damage = self._actual_image_damage + \
                              self._actual_css_damage + \
                              self._actual_js_damage + \
                              self._actual_multimedia_damage + \
                              self._actual_text_damage + \
                              self._actual_iframe_damage

        self._logger.info('Actual damage of {} is {}'.format('"webpage"', self._actual_damage))

    def _calculate_image_and_multimedia_damage(self, log, size_weight=0.5, centrality_weight=0.5,
                                               use_viewport_size=True):
        importances = []

        # im = Image.open(self.screenshot_file)
        viewport_w, viewport_h = self.viewport_size if use_viewport_size else self.page_size

        # A line in *.img.log representate an image
        # An image can be appeared in more than one location in page
        # Location and size is saved in 'rectangles'
        for image_rect in log['rectangles']:
            # Based on measureMemento.pl line 690
            x = image_rect['left']
            y = image_rect['top']
            w = image_rect['width']
            h = image_rect['height']

            importance, location_importance, size_importance = self._calculate_block_importance(
                (x, y), (w, h), (viewport_w, viewport_h), (centrality_weight, size_weight))
            importances.append((location_importance, size_importance, importance))

        return importances

    def _calculate_css_damage(self, log, tag_weight=0.5, ratio_weight=0.5,
                              is_potential=False, use_viewport_size=True):
        css_url = log['url']
        rules_importance = log['importance']

        # I think it have no implication, since all css status_code is 404
        # if 'status_code' not in log:
        #     status_code = 404
        # else:
        #     status_code, true =  log['status_code']
        #
        # # Based on measureMemento.pl line 760
        # if status_code == 200:
        #     return 1
        #
        # # If status_code is started with 3xx
        # # Based on measureMemento.pl line 764
        # if str(status_code)[0] == '3':
        #     return 0

        tag_importance = 0.0
        ratio_importance = 0.0
        total_importance = 0.0

        if True:
            # Based on measureMemento.pl line 771
            if rules_importance > 0:
                tag_importance = tag_weight

            # Based on measureMemento.pl line 777
            if not is_potential:
                # Code below is a subtitution for Justin's whitespace.pl
                # Open screenshot file
                # screenshot_file = os.path.join(self.screenshot_dir,
                #                                '{}.png'.format(log['hash']))
                im = Image.open(self.memento_damage.screenshot_file)
                # Get all pixels
                pix = im.load()
                # np_pic = numpy.asarray(im)

                # Use vieport_size (screenshot size) or default_window_size (
                # 1024x768)
                viewport_w, viewport_h = self.viewport_size if use_viewport_size else self.page_size
                # windows_h, window_w, _ = np_pic.shape

                # Whiteguys is representation of pixels having same color with
                # background color
                whiteguys_col = {}

                # Iterate over pixels in window size (e.g. 1024x768)
                # And check whether having same color with background
                for x in range(0, viewport_w):
                    whiteguys_col.setdefault(x, 0)
                    for y in range(0, viewport_h):
                        # Get RGBA color in each pixel
                        #     (e.g. White -> (255,255,255,255))
                        r_, g_, b_, a_ = pix[x, y]
                        # r_, g_, b_, a_ = np_pic[y,x]
                        # Convert RGBA to Hex color
                        #     (e.g. White -> FFFFFF)
                        pix_hex = self._rgb2hex(r_, g_, b_)

                        if pix_hex.upper() == \
                                self.memento_damage.background_color.upper():
                            whiteguys_col[x] += 1

                # divide width into 3 parts
                # Justin use term : low, mid, and high for 1/3 left,
                # 1/3 midlle, and 1/3 right
                one_third = int(math.floor(viewport_w / 3))

                # calculate whiteguys in the 1/3 left
                leftWhiteguys = 0
                for c in range(0, one_third):
                    leftWhiteguys += whiteguys_col[c]
                left_avg = leftWhiteguys / one_third

                # calculate whiteguys in the 1/3 center
                centerWhiteguys = 0
                for c in range(one_third, 2 * one_third):
                    centerWhiteguys += whiteguys_col[c]
                center_avg = centerWhiteguys / one_third

                # calculate whiteguys in the 1/3 right
                rightWhiteguys = 0
                for c in range(2 * one_third, viewport_w):
                    rightWhiteguys += whiteguys_col[c]
                right_avg = rightWhiteguys / one_third

                # Based on measureMemento.pl line 803
                # give tolerance 0.05% from total whiteguys average
                right_avg_tolerance = 0.05 * (left_avg + center_avg + right_avg)
                if (left_avg + center_avg + right_avg) == 0:
                    ratio_importance = 0.0
                elif float(right_avg + right_avg_tolerance) / (left_avg + center_avg + right_avg) > \
                                float(1) / 3:
                    ratio_importance = float(right_avg) / (
                        left_avg + center_avg + right_avg) * ratio_weight
                else:
                    ratio_importance = ratio_weight


            # Based on measureMemento.pl line 819
            else:
                ratio_importance = ratio_weight

        total_importance = tag_importance + ratio_importance
        return (tag_importance, ratio_importance, total_importance)

    def _calculate_text_damage(self, log, size_weight=0.5, centrality_weight=0.5, use_viewport_size=True):
        importances = []

        viewport_w, viewport_h = self.viewport_size if use_viewport_size else self.page_size

        if len(log['text']) > 0:
            x = log['left']
            y = log['top']
            w = log['width']
            h = log['height']
            c = log['coverage']

            importance, location_importance, size_importance = self._calculate_block_importance(
                (x, y), (w, h), (viewport_w, viewport_h), (centrality_weight, size_weight), alt_coverage=c)
            importances.append((location_importance, size_importance, importance))

        return importances

    def _calculate_iframe_damage(self, log, size_weight=0.5, centrality_weight=0.5, use_viewport_size=True):
        importances = []

        viewport_w, viewport_h = self.viewport_size if use_viewport_size else self.page_size
        x = log['left']
        y = log['top']
        w = log['width']
        h = log['height']

        importance, location_importance, size_importance = self._calculate_block_importance(
            (x, y), (w, h), (viewport_w, viewport_h), (centrality_weight, size_weight),
            alt_coverage=log['coverage'] if 'coverage' in log else None)

        if 'important' in log and not log['important']:
            location_importance = 0.0

        importances.append((location_importance, size_importance, importance))

        return importances

    def _calculate_block_importance(self, (x, y), (w, h), (viewport_w, viewport_h),
                                    (location_weight, size_weight), alt_coverage=None):
        middle_x = float(viewport_w) / 2
        middle_y = float(viewport_h) / 2

        location_importance = 0.0
        size_importance = 0.0

        # New algorithm, need to be tested
        '''
        if x and y and w and h:
            text_middle_x = float(x + w) / 2
            text_middle_y = float(y + h) / 2

            if float(x + w) >= 0.0 and float(y + h) >= 0.0:
                distance_x = abs(middle_x - text_middle_x)
                distance_y = abs(middle_y - text_middle_y)

                prop_x = (middle_x - distance_x) / middle_x
                prop_y = (middle_y - distance_y) / middle_y

                location_importance += prop_x * (centrality_weight / 2)
                location_importance += prop_y * (centrality_weight / 2)
        '''

        # Location Importance
        # Based on measureMemento.pl line 703
        if (x + w) > middle_x and x < middle_x:  # if it crosses the vertical center
            location_importance += location_weight / 2;

        # Based on measureMemento.pl line 715
        if (y + h) > middle_y and y < middle_y:  # if it crosses the horizontal center
            location_importance += location_weight / 2;

        # Size Importance
        coverage = float(w) * h
        if alt_coverage:
            coverage = float(alt_coverage)

        if viewport_w * viewport_h > 0:
            prop = coverage / (viewport_w * viewport_h)
            size_importance = prop * size_weight

        return location_importance + size_importance, location_importance, size_importance

    def _rgb2hex(self, r, g, b):
        return '{:02x}{:02x}{:02x}'.format(r, g, b).upper()
