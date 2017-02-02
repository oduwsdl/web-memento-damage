import io
import json
import math
import urlparse

import html2text
from PIL import Image


class MementoDamageAnalysis(object):
    image_importance = {}
    css_importance = 0

    multimedia_weight   = 0.50
    css_weight          = 0.05
    proportion          = 3.0/4.0
    image_weight        = proportion * (1-(multimedia_weight + css_weight))
    text_weight         = 1.0 - (multimedia_weight + css_weight + image_weight)
    words_per_image     = 1000

    blacklisted_uris = [
        'https://analytics.archive.org/',
        '[INTERNAL]'
    ]

    def __init__(self, memento_damage):
        self.memento_damage = memento_damage

        # Read log contents
        h = html2text.HTML2Text()
        h.ignore_links = True
        self._text = h.handle(u' '.join([line.strip() for line in io.open(memento_damage.html_file, encoding="utf-8").readlines()]))
        self._logs = [json.loads(log, strict=False) for log in io.open(memento_damage.network_log_file, encoding="utf-8").readlines()]
        self._image_logs = [json.loads(log, strict=False) for log in io.open(memento_damage.image_log_file, encoding="utf-8").readlines()]
        self._css_logs = [json.loads(log, strict=False) for log in io.open(memento_damage.css_log_file, encoding="utf-8").readlines()]
        self._mlm_logs = [json.loads(log, strict=False) for log in io.open(memento_damage.video_log_file, encoding="utf-8").readlines()]
        self._text_logs = {}

        self._logger = self.memento_damage.logger

    def run(self):
        # Filter blacklisted uris
        self._remove_blacklisted_uris()
        self._resolve_uri_redirection()

        self._calculate_percentage_coverage()
        self._find_missing_uris()

        self._logger.info('Start calculating damage...')

        self._calculate_potential_damage()
        self._calculate_actual_damage()

        self._logger.info('Done calculating damage')

    def get_result(self):
        logs = {}
        for log in self._logs:
            logs[log['url']] = log

        redirect_uris = []
        self._follow_redirection(self.memento_damage.uri, logs, redirect_uris)
        final_uri, final_status_code = redirect_uris[len(redirect_uris) - 1]

        if (not final_status_code) or (final_status_code != 200):
            total_damage = 1
        elif self._potential_damage != 0:
            total_damage = self._actual_damage / self._potential_damage
        else:
            total_damage = 0

        self._logger.info('Calculate total damage (actual damage / potential damage) = {}'.format(total_damage))


        result = {}
        result['uri'] = self.memento_damage.uri
        result['weight'] = {
            'multimedia': self.multimedia_weight,
            'css': self.css_weight,
            'image': self.image_weight,
            'text': self.text_weight
        }
        result['images'] = self._image_logs
        result['csses'] = self._css_logs
        result['multimedias'] = self._mlm_logs
        result['text'] = self._text_logs
        result['potential_damage'] = {
            'total': self._potential_damage,
            'image': self._potential_image_damage,
            'css': self._potential_css_damage,
            'multimedia': self._potential_multimedia_damage,
            'text': self._potential_damage_text,
        }
        result['actual_damage'] = {
            'total': self._actual_damage,
            'image': self._actual_image_damage,
            'css': self._actual_css_damage,
            'multimedia': self._actual_multimedia_damage,
            'text': self._actual_damage_text,
        }
        result['total_damage'] = total_damage
        result['redirect_uris'] = redirect_uris
        result['error'] = False
        result['is_archive'] = False

        return result

    def get_result_as_string(self):
        return json.dumps(self.get_result(), indent=4)

    def _is_blacklisted(self, log):
        is_blacklisted = False

        # Check whether uri is defined in blacklisted_uris
        for b_uri in self.blacklisted_uris:
            if log['url'].startswith(b_uri):
                is_blacklisted = True
                break

        # If not defined, check whether uri has header 'Link' containing
        # <http://mementoweb.org/terms/donotnegotiate>; rel="type"
        if 'headers' in log and 'Link' in log['headers'] and not is_blacklisted:
            if log['headers']['Link'] == '<http://mementoweb.org/terms/' \
                                         'donotnegotiate>; rel="type"':
                is_blacklisted = True

        return is_blacklisted

    def _remove_blacklisted_uris(self):
        # Filter images log
        tmp_image_logs = []
        for log in self._image_logs:
            # If not blacklisted, put into temporary array
            if not self._is_blacklisted(log):
                tmp_image_logs.append(log)

        self._image_logs = tmp_image_logs

        # Filter multimedia log
        tmp_mlm_logs = []
        for log in self._mlm_logs:
            # If not blacklisted, put into temporary array
            if not self._is_blacklisted(log):
                tmp_mlm_logs.append(log)

        self._mlm_logs = tmp_mlm_logs

        # Filter csses log
        tmp_css_logs = []
        for log in self._css_logs:
            # If not blacklisted, put into temporary array
            if not self._is_blacklisted(log):
                tmp_css_logs.append(log)

        self._css_logs = tmp_css_logs

        self._logger.info('Remove blacklisted URIS')
        self._logger.info('Blacklisted URIS: {}'.format(', '.join(self.blacklisted_uris)))

    def _resolve_uri_redirection(self):
        logs = {}
        for log in self._logs:
            logs[log['url']] = log

        # Resolve redirection for image
        self._image_logs = self._purify_logs(self._image_logs, logs)

        # Resolve redirection for multimedia
        self._mlm_logs = self._purify_logs(self._mlm_logs, logs)

        # Resolve redirection for css
        self._css_logs = self._purify_logs(self._css_logs, logs)

        self._logger.info('Resolve URI redirection')

    def _purify_logs(self, source_logs, logs):
        log_obj = {}
        for log in source_logs:
            log_obj[log['url']] = log

        final_uris = []
        for log in source_logs:
            uri = log['url']

            redirect_uris = []
            self._follow_redirection(uri, logs, redirect_uris)

            if len(redirect_uris) > 0:
                original_uri, original_status = redirect_uris[0]
                final_uri, final_status_code = redirect_uris[len(redirect_uris)-1]

                if original_uri != final_uri:
                    log_obj[original_uri]['url'] = final_uri
                    log_obj[original_uri]['status_code'] = final_status_code
                    final_uris.append(final_uri)

        for uri in final_uris:
            log_obj.pop(uri, 0)

        return log_obj.values()

    def _follow_redirection(self, uri, logs, redirect_uris):
        uri = unicode(uri)
        while True:
            if uri.endswith('/'):
                slashed_uri = uri
                unslashed_uri = slashed_uri[:-1]
            else:
                unslashed_uri = uri
                slashed_uri = uri + '/'

            line = None
            if unslashed_uri in logs.keys():
                line = logs[unslashed_uri]
            elif slashed_uri in logs.keys():
                line = logs[slashed_uri]

            if line:
                status_code = line['status_code']
                redirect_uris.append((uri, status_code))

                if status_code in [301, 302]:
                    redirect_url = line['headers']['Location']
                    uri = urlparse.urljoin(uri, redirect_url)
                else:
                    break
            else:
                break

    def _calculate_percentage_coverage(self):
        # Coverage of images
        for idx, log in enumerate(self._image_logs):
            viewport_w, vieport_h = log['viewport_size']
            image_coverage  = 0
            for rect in log['rectangles']:
                w = rect['width']
                h = rect['height']
                image_coverage += (w * h)

            if float(viewport_w * vieport_h) > 0:
                pct_image_coverage = float(image_coverage) / \
                                     float(viewport_w * vieport_h)
            else: pct_image_coverage = 0.0

            self._image_logs[idx]['percentage_coverage'] = pct_image_coverage

        # Coverage of videos
        for idx, log in enumerate(self._mlm_logs):
            viewport_w, vieport_h = log['viewport_size']
            mlm_coverage  = 0
            for rect in log['rectangles']:
                w = rect['width']
                h = rect['height']
                mlm_coverage += (w * h)

            pct_mlm_coverage = float(mlm_coverage) / \
                                 float(viewport_w * vieport_h)
            self._mlm_logs[idx]['percentage_coverage'] = pct_mlm_coverage

        self._logger.info('Calculate percentage coverage')

    def _find_missing_uris(self):
        self._logger.info('Find missing URIS')

        self.missing_imgs_log = []
        for log in self._image_logs:
            if log['status_code'] > 399:
                self.missing_imgs_log.append(log)

        self.missing_mlms_log = []
        for log in self._mlm_logs:
            if log['status_code'] > 399:
                self.missing_mlms_log.append(log)

        # self.missing_csses_log = []
        # for log in self.csses_log:
        #     if 'status_code' in log:
        #         status_code, true = log['status_code']
        #         if status_code > 399:
        #             self.missing_csses_log.append(log)

        # Since all css set to 404 (missing)
        self.missing_csses_log = self._css_logs

    def _calculate_potential_damage(self):
        self._logger.info('Calculating potential damage')

        # Image
        self._logger.info('Calculate potential damage for Image(s)')

        total_images_damage = 0
        for idx, log in enumerate(self._image_logs):
            image_damage = self._calculate_image_damage(log)
            # Based on measureMemento.pl line 463
            total_location_importance = 0
            total_size_importance = 0
            total_image_damage = 0
            for location_importance, size_importance, damage in image_damage:
                total_location_importance += location_importance
                total_size_importance += size_importance
                total_image_damage += damage

            total_images_damage += total_image_damage

            self._image_logs[idx]['potential_damage'] = {
                'location' : total_location_importance,
                'size' : total_size_importance,
                'total' : total_image_damage
            }

            self._logger.info('Potential damage of {} is {}'.format(log['url'], total_image_damage))
            # print('Potential damage {} for {}'
            #       .format(total_image_damage, log['url']))

        # Css
        self._logger.info('Calculate potential damage for Stylesheet(s)')

        total_css_damage = 0
        for idx, log in enumerate(self._css_logs):
            tag_importance, ratio_importance, css_damage = \
                self._calculate_css_damage(log, use_window_size=False, \
                                           is_potential=True)

            # Based on measureMemento.pl line 468
            total_css_damage += css_damage

            self._css_logs[idx]['potential_damage'] = {
                'tag'   : tag_importance,
                'ratio' : ratio_importance,
                'total' : css_damage
            }
            self._logger.info('Potential damage of {} is {}'.format(log['url'], css_damage))
            # print('Potential damage {} for {}'.format(css_damage, log['url']))

        # Multimedia
        self._logger.info('Calculate potential damage for Multimedia(s)')

        total_mlms_damage = 0
        for idx, log in enumerate(self._mlm_logs):
            css_damage = self._calculate_image_damage(log)
            # Based on measureMemento.pl line 463
            total_location_importance = 0
            total_size_importance = 0
            total_mlm_damage = 0
            for location_importance, size_importance, damage in css_damage:
                total_location_importance += location_importance
                total_size_importance += size_importance
                total_mlm_damage += damage

            total_mlms_damage += total_mlm_damage

            self._mlm_logs[idx]['potential_damage'] = {
                'location' : total_location_importance,
                'size' : total_size_importance,
                'total' : total_mlm_damage
            }

            self._logger.info('Potential damage of {} is {}'.format(log['url'], total_mlm_damage))
            # print('Potential damage {} for {}'
            #       .format(total_mlm_damage, log['url']))

        # Text
        self._logger.info('Calculate potential damage for Text')

        num_words_of_text = len(self._text.split())
        total_text_damage = float(num_words_of_text) / self.words_per_image

        self._text_logs['num_words'] = num_words_of_text
        self._text_logs['words_per_image'] = self.words_per_image

        self._logger.info('Potential damage of {} is {}'.format('"text"', total_text_damage))
        # print('Potential damage {} for {}'.format(total_text_damage, 'text'))

        # Based on measureMemento.pl line 555
        self._logger.info('Weighting potential damage(s)')

        self._potential_image_damage = total_images_damage * self.image_weight
        self._potential_css_damage = total_css_damage * self.css_weight
        self._potential_multimedia_damage = total_mlms_damage * \
                                            self.multimedia_weight
        self._potential_damage_text = total_text_damage * self.text_weight

        self._potential_damage = self._potential_image_damage + \
                                 self._potential_css_damage + \
                                 self._potential_multimedia_damage + \
                                 self._potential_damage_text

        self._logger.info('Potential damage of {} is {}'.format('"webpage"', self._potential_damage))

    def _calculate_actual_damage(self):
        self._logger.info('Calculating actual damage')

        # Images
        self._logger.info('Calculate actual damage for Image(s)')

        total_images_damage = 0
        for idx, log in enumerate(self._image_logs):
            if log['status_code'] > 399:
                image_damage = self._calculate_image_damage(log)
                # Based on measureMemento.pl line 463
                total_location_importance = 0
                total_size_importance = 0
                total_image_damage = 0
                for location_importance, size_importance, damage in image_damage:
                    total_location_importance += location_importance
                    total_size_importance += size_importance
                    total_image_damage += damage

                total_images_damage += total_image_damage

                self._image_logs[idx]['actual_damage'] = {
                    'location' : total_location_importance,
                    'size' : total_size_importance,
                    'total' : total_image_damage
                }

                self._logger.info('Actual damage of {} is {}'.format(log['url'], total_image_damage))
                # print('Actual damage {} for {}'
                #       .format(total_image_damage, log['url']))

        # Css
        self._logger.info('Calculate actual damage for Stylesheet(s)')

        total_css_damage = 0
        for idx, log in enumerate(self._css_logs):
            tag_importance, ratio_importance, css_damage = \
                self._calculate_css_damage(log, use_window_size=False)

            # Based on measureMemento.pl line 468
            total_css_damage += css_damage

            self._css_logs[idx]['actual_damage'] = {
                'tag'   : tag_importance,
                'ratio' : ratio_importance,
                'total' : css_damage
            }

            self._logger.info('Actual damage of {} is {}'.format(log['url'], css_damage))
            # print('Actual damage {} for {}'.format(css_damage, log['url']))

        # Multimedia
        self._logger.info('Calculate actual damage for Multimedia(s)')

        total_mlms_damage = 0
        for idx, log in enumerate(self._mlm_logs):
            if log['status_code'] > 399:
                mlm_damage = self._calculate_image_damage(log)
                # Based on measureMemento.pl line 463
                total_location_importance = 0
                total_size_importance = 0
                total_mlm_damage = 0
                for location_importance, size_importance, damage in mlm_damage:
                    total_location_importance += location_importance
                    total_size_importance += size_importance
                    total_mlm_damage += damage

                total_mlms_damage += total_mlm_damage

                self._mlm_logs[idx]['actual_damage'] = {
                    'location' : total_location_importance,
                    'size' : total_size_importance,
                    'total' : total_mlm_damage
                }

                self._logger.info('Actual damage of {} is {}'.format(log['url'], total_mlm_damage))
                # print('Actual damage {} for {}'
                #       .format(total_mlm_damage, log['url']))

        # Text
        total_text_damage = 0
        self._actual_damage_text = total_text_damage * self.text_weight

        self._logger.info('Actual damage of {} is {}'.format('"text"', self._actual_damage_text))
        # print('Actual damage {} for {}'.format(self.actual_damage_text, 'text'))

        # Based on measureMemento.pl line 555
        self._logger.info('Weighting actual damage(s)')

        self._actual_image_damage = total_images_damage * self.image_weight
        self._actual_css_damage = total_css_damage * self.css_weight
        self._actual_multimedia_damage = total_mlms_damage * \
                                         self.multimedia_weight
        self._actual_damage = self._actual_image_damage + \
                              self._actual_css_damage + \
                              self._actual_multimedia_damage + \
                              self._actual_damage_text

        self._logger.info('Actual damage of {} is {}'.format('"webpage"', self._actual_damage))

    def _calculate_image_damage(self, log, size_weight=0.5,
                                centrality_weight=0.5):
        importances = []

        #im = Image.open(self.screenshot_file)
        viewport_w, viewport_h = log['viewport_size'] #im.size
        middle_x = viewport_w / 2
        middle_y = viewport_h / 2

        # A line in *.img.log representate an image
        # An image can be appeared in more than one location in page
        # Location and size is saved in 'rectangles'
        for image_rect in log['rectangles']:
            # Based on measureMemento.pl line 690
            x = image_rect['left']
            y = image_rect['top']
            w = image_rect['width']
            h = image_rect['height']

            location_importance = 0.0
            # Based on measureMemento.pl line 703
            if (x + w) > middle_x and x < middle_x:
                location_importance += centrality_weight / 2;

            # Based on measureMemento.pl line 715
            if (y + h) > middle_y and y < middle_y:
                location_importance += centrality_weight / 2;

            if viewport_w * viewport_h > 0:
                prop = float(w * h) / (viewport_w * viewport_h)
            else: prop = 0

            size_importance = prop * size_weight

            importance = location_importance + size_importance
            importances.append((location_importance, size_importance,
                                importance))

        return importances

    def _calculate_css_damage(self, log, tag_weight=0.5, ratio_weight=0.5,
                              is_potential=False, use_window_size = True,
                              window_size=(1024,768)):
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
                window_w, windows_h = window_size
                if not use_window_size:
                    window_w, window_h = im.size
                    # windows_h, window_w, _ = np_pic.shape

                # Whiteguys is representation of pixels having same color with
                # background color
                whiteguys_col = {}

                # Iterate over pixels in window size (e.g. 1024x768)
                # And check whether having same color with background
                for x in range(0,window_w):
                    whiteguys_col.setdefault(x, 0)
                    for y in range(0,windows_h):
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
                one_third = int(math.floor(window_w/3))

                # calculate whiteguys in the 1/3 left
                leftWhiteguys = 0
                for c in range(0,one_third):
                    leftWhiteguys += whiteguys_col[c]
                left_avg = leftWhiteguys / one_third

                # calculate whiteguys in the 1/3 center
                centerWhiteguys = 0
                for c in range(one_third,2*one_third):
                    centerWhiteguys += whiteguys_col[c]
                center_avg = centerWhiteguys / one_third

                # calculate whiteguys in the 1/3 right
                rightWhiteguys = 0
                for c in range(2*one_third,window_w):
                    rightWhiteguys += whiteguys_col[c]
                right_avg = rightWhiteguys / one_third

                # Based on measureMemento.pl line 803
                # give tolerance 0.05% from total whiteguys average
                right_avg_tolerance = 0.05 * (left_avg + center_avg + right_avg)
                if (left_avg + center_avg + right_avg) == 0:
                    ratio_importance = 0.0
                elif float(right_avg + right_avg_tolerance) / (left_avg + center_avg + right_avg) > \
                        float(1)/3:
                    ratio_importance = float(right_avg) / (
                        left_avg + center_avg + right_avg) * ratio_weight
                else:
                    ratio_importance = ratio_weight


            # Based on measureMemento.pl line 819
            else:
                ratio_importance = ratio_weight

        total_importance = tag_importance + ratio_importance
        return (tag_importance, ratio_importance, total_importance)


    def _rgb2hex(self, r, g, b):
        return '{:02x}{:02x}{:02x}'.format(r, g, b).upper()