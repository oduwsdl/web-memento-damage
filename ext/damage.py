'''
Section 'Damage' =============================================================
'''
import math
from PIL import Image
from hashlib import md5
import html2text


def rgb2hex(r, g, b):
    return '{:02x}{:02x}{:02x}'.format(r, g, b).upper()

class SiteDamage:
    image_importance = {}
    css_importance = 0

    multimedia_weight   = 0.50
    css_weight          = 0.05
    proportion          = 3.0/4.0
    image_weight        = proportion * (1-(multimedia_weight + css_weight))
    text_weight         = 1.0 - (multimedia_weight + css_weight + image_weight)
    words_per_image     = 1000

    blacklisted_uris = [
        'https://analytics.archive.org/'
    ]

    def __init__(self, text, logs, image_logs, css_logs, screenshot_file,
                 background_color = 'FFFFFF'):
        self.text = text
        self.logs = logs
        self.image_logs = image_logs
        self.css_logs = css_logs
        self.screenshot_file = os.path.abspath(screenshot_file)
        self.background_color = background_color

        # Filter blacklisted uris
        self.filter_blacklisted_uris()
        self.resolve_redirection()

        pct_cov = self.get_percentage_coverage()
        #print('Percentage COverage = {}'.format(pct_cov))

        self.find_missings()
        #print('Missing images = {}'.format(self.missing_imgs_log))
        #print('Missing csses = {}'.format(self.missing_csses_log))

    def filter_blacklisted_uris(self):
        # Filter images log
        tmp_image_logs = []
        for log in self.image_logs:
            is_blacklisted = False

            # Check whether uri is defined in blacklisted_uris
            for b_uri in self.blacklisted_uris:
                if log['url'].startswith(b_uri):
                    is_blacklisted = True
                    break

            # If not defined, check whether uri has header 'Link' containing
            # <http://mementoweb.org/terms/donotnegotiate>; rel="type"
            if 'Link' in log['headers'] and not is_blacklisted:
                if log['headers']['Link'] == '<http://mementoweb.org/terms/' \
                                             'donotnegotiate>; rel="type"':
                    is_blacklisted = True

            # If not blacklisted, put into temporary array
            if not is_blacklisted:
                tmp_image_logs.append(log)

        self.image_logs = tmp_image_logs

        # Filter csses log
        tmp_css_logs = []
        for log in self.css_logs:
            is_blacklisted = False

            # Check whether uri is defined in blacklisted_uris
            for b_uri in self.blacklisted_uris:
                if log['url'].startswith(b_uri):
                    is_blacklisted = True
                    break

            # If not defined, check whether uri has header 'Link' containing
            # <http://mementoweb.org/terms/donotnegotiate>; rel="type"
            if 'headers' in log and 'Link' in log['headers'] \
                    and not is_blacklisted:
                if log['headers']['Link'] == '<http://mementoweb.org/terms/' \
                                             'donotnegotiate>; rel="type"':
                    is_blacklisted = True

            # If not blacklisted, put into temporary array
            if not is_blacklisted:
                tmp_css_logs.append(log)

        self.css_logs = tmp_css_logs

    def resolve_redirection(self):
        logs = {}
        for log in self.logs:
            logs[log['url']] = log

        # Resolve redirection for image
        images_log = {}
        for log in self.image_logs:
            images_log[log['url']] = log

        purified_image_logs = {}
        for log in self.image_logs:
            uri = log['url']

            redirect_uris = []
            self.follow_redirection(uri, images_log, redirect_uris)

            if len(redirect_uris) > 0:
                original_uri, original_status = redirect_uris[0]
                final_uri, final_status_code = redirect_uris[len(redirect_uris)-1]

                if original_status == 302 and final_uri in logs:
                    purified_image_logs[final_uri] = logs[final_uri]
                    # Add entries from original uri
                    purified_image_logs[final_uri]['rectangles'] = \
                        images_log[original_uri]['rectangles']
                    purified_image_logs[final_uri]['viewport_size'] = \
                        images_log[original_uri]['viewport_size']

                elif original_uri not in purified_image_logs:
                    purified_image_logs[original_uri] = images_log[original_uri]

        self.image_logs = purified_image_logs.values()

        # Resolve redirection for css
        css_logs = {}
        for log in self.css_logs:
            css_logs[log['url']] = log

        purified_css_logs = {}
        for log in self.css_logs:
            uri = log['url']

            redirect_uris = []
            self.follow_redirection(uri, logs, redirect_uris)

            if len(redirect_uris) > 0:
                original_uri, original_status = redirect_uris[0]
                final_uri, final_status_code = redirect_uris[len(redirect_uris)-1]

                if original_status == 302 and final_uri in logs:
                    purified_css_logs[final_uri] = logs[final_uri]
                    # Add entries from original uri
                    purified_css_logs[final_uri]['rules_tag'] = \
                        css_logs[original_uri]['rules_tag']
                    purified_css_logs[final_uri]['importance'] = \
                        css_logs[original_uri]['importance']

                elif original_uri not in purified_css_logs:
                    purified_css_logs[original_uri] = css_logs[original_uri]

        self.css_logs = purified_css_logs.values()

    def follow_redirection(self, uri, logs, redirect_uris):
        if uri in logs:
            redirect_uris.append((uri, logs[uri]['status_code']
                if 'status_code' in logs[uri] else ''))

            if 'status_code' in logs[uri] and logs[uri]['status_code'] == 302:
                redirect_uri = logs[uri]['headers']['Location']

                for r_uri in logs.keys():
                    if r_uri != uri and r_uri.endswith(redirect_uri):
                        redirect_uri = r_uri
                        break

                self.follow_redirection(redirect_uri, logs, redirect_uris)

    def get_percentage_coverage(self):
        pct_images_coverage = 0.0
        for idx, log in enumerate(self.image_logs):
            viewport_w, vieport_h = log['viewport_size']
            image_coverage  = 0
            for rect in log['rectangles']:
                w = rect['width']
                h = rect['height']
                image_coverage += (w * h)

            pct_image_coverage = float(image_coverage) / \
                                 float(viewport_w * vieport_h)
            self.image_logs[idx]['percentage_coverage'] = pct_image_coverage

            pct_images_coverage += pct_image_coverage

        return pct_images_coverage

    def find_missings(self):
        self.missing_imgs_log = []
        for log in self.image_logs:
            if log['status_code'] > 399:
                self.missing_imgs_log.append(log)

        # self.missing_csses_log = []
        # for log in self.csses_log:
        #     if 'status_code' in log:
        #         status_code, true = log['status_code']
        #         if status_code > 399:
        #             self.missing_csses_log.append(log)

        # Since all css set to 404 (missing)
        self.missing_csses_log = self.css_logs

    def calculate_all(self):
        self.calculate_potential_damage()
        self.calculate_actual_damage()

    def calculate_potential_damage(self):
        # Image
        total_images_damage = 0
        for idx, log in enumerate(self.image_logs):
            image_damage = self.calculate_image_damage(log)
            # Based on measureMemento.pl line 463
            total_location_importance = 0
            total_size_importance = 0
            total_image_damage = 0
            for location_importance, size_importance, damage in image_damage:
                total_location_importance += location_importance
                total_size_importance += size_importance
                total_image_damage += damage

            total_images_damage += total_image_damage

            self.image_logs[idx]['potential_damage'] = {
                'location' : total_location_importance,
                'size' : total_size_importance,
                'total' : total_image_damage
            }
            print('Potential damage {} for {}'
                  .format(total_image_damage, log['url']))

        # Css
        total_css_damage = 0
        for idx, log in enumerate(self.css_logs):
            tag_importance, ratio_importance, css_damage = \
                self.calculate_css_damage(log, use_window_size=False, \
                                          is_potential=True)

            # Based on measureMemento.pl line 468
            total_css_damage += css_damage

            self.css_logs[idx]['potential_damage'] = {
                'tag'   : tag_importance,
                'ratio' : ratio_importance,
                'total' : css_damage
            }
            print('Potential damage {} for {}'.format(css_damage, log['url']))

        # Text
        words = self.text.split()
        total_text_damage = float(len(words)) / self.words_per_image
        print('Potential damage {} for {}'.format(total_text_damage, 'text'))

        # Based on measureMemento.pl line 555
        self.potential_image_damage = total_images_damage * self.image_weight
        self.potential_css_damage = total_css_damage * self.css_weight
        self.potential_damage_text = total_text_damage * self.text_weight

        self.potential_damage = self.potential_image_damage + \
                                self.potential_css_damage + \
                                self.potential_damage_text

    def calculate_actual_damage(self):
        # Images
        total_images_damage = 0
        for idx, log in enumerate(self.image_logs):
            if log['status_code'] > 399:
                image_damage = self.calculate_image_damage(log)
                # Based on measureMemento.pl line 463
                total_location_importance = 0
                total_size_importance = 0
                total_image_damage = 0
                for location_importance, size_importance, damage in image_damage:
                    total_location_importance += location_importance
                    total_size_importance += size_importance
                    total_image_damage += damage

                total_images_damage += total_image_damage

                self.image_logs[idx]['actual_damage'] = {
                    'location' : total_location_importance,
                    'size' : total_size_importance,
                    'total' : total_image_damage
                }
                print('Actual damage {} for {}'
                      .format(total_image_damage, log['url']))

        # Css
        total_css_damage = 0
        for idx, log in enumerate(self.css_logs):
            tag_importance, ratio_importance, css_damage = \
                self.calculate_css_damage(log, use_window_size=False)

            # Based on measureMemento.pl line 468
            total_css_damage += css_damage

            self.css_logs[idx]['actual_damage'] = {
                'tag'   : tag_importance,
                'ratio' : ratio_importance,
                'total' : css_damage
            }
            print('Actual damage {} for {}'.format(css_damage, log['url']))

        # Text
        total_text_damage = 0
        self.actual_damage_text = total_text_damage * self.text_weight

        # Based on measureMemento.pl line 555
        self.actual_image_damage = total_images_damage * self.image_weight
        self.actual_css_damage = total_css_damage * self.css_weight
        self.actual_damage = self.actual_image_damage + \
                             self.actual_css_damage + self.actual_damage_text

    def calculate_image_damage(self, log, size_weight=0.5,
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

            prop = float(w * h) / (viewport_w * viewport_h)
            size_importance = prop * size_weight

            importance = location_importance + size_importance
            importances.append((location_importance, size_importance,
                                importance))

        return importances

    def calculate_css_damage(self, log, tag_weight=0.5, ratio_weight=0.5,
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

        if is_potential or (not is_potential and
                            'status_code' in log and log['status_code'] > 399):
            # Based on measureMemento.pl line 771
            if rules_importance > 0:
                tag_importance = tag_weight

            # Based on measureMemento.pl line 777
            if not is_potential:
                # Code below is a subtitution for Justin's whitespace.pl
                # Open screenshot file
                im = Image.open(self.screenshot_file)
                # Get all pixels
                pix = im.load()

                # Use vieport_size (screenshot size) or default_window_size (
                # 1024x768)
                if not use_window_size:
                    window_size = im.size

                window_w, windows_h = window_size

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
                        r_, g_, b_, a_ = pix[x,y]
                        # Convert RGBA to Hex color
                        #     (e.g. White -> FFFFFF)
                        pix_hex = rgb2hex(r_, g_, b_)

                        if pix_hex.upper() == \
                                self.background_color.upper():
                            whiteguys_col[x] += 1

                # divide width into 3 parts
                # Justin use term : low, mid, and high for 1/3 left,
                # 1/3 midlle, and 1/3 right
                one_third = int(math.floor(window_w/3))

                # calculate whiteguys in the 1/3 left
                leftWhiteguys = 0
                for c in range(0,one_third):
                    leftWhiteguys += whiteguys_col[c]
                leftAvg = leftWhiteguys / one_third

                # calculate whiteguys in the 1/3 center
                centerWhiteguys = 0
                for c in range(one_third,2*one_third):
                    centerWhiteguys += whiteguys_col[c]
                centerAvg = centerWhiteguys / one_third

                # calculate whiteguys in the 1/3 right
                rightWhiteguys = 0
                for c in range(2*one_third,window_w):
                    rightWhiteguys += whiteguys_col[c]
                rightAvg = rightWhiteguys / one_third

                # Based on measureMemento.pl line 803
                if (leftAvg + centerAvg + rightAvg) == 0:
                    ratio_importance = 0.0
                elif float(rightAvg) / (leftAvg+centerAvg+rightAvg) > \
                        float(1)/3:
                    ratio_importance = float(rightAvg) / (
                        leftAvg+centerAvg+rightAvg) * ratio_weight
                else:
                    ratio_importance = ratio_weight


            # Based on measureMemento.pl line 819
            else:
                ratio_importance = ratio_weight

        total_importance = tag_importance + ratio_importance
        return (tag_importance, ratio_importance, total_importance)

if __name__ == "__main__":
    import sys
    import os
    import json

    if len(sys.argv) > 0:
        if len(sys.argv) < 3:
            print('Usage :')
            print('python damage.py <uri> <cache_dir> <background_color>')
            exit()

        # Read arguments
        uri = sys.argv[1]
        output_dir = sys.argv[2]
        background_color = sys.argv[3] if len(sys.argv) >= 3 else 'FFFFFF'

        hashed_url = md5(uri).hexdigest()

        # Resolve file path
        html_file = os.path.join(output_dir, 'html',
                                 '{}.html'.format(hashed_url))
        log_file = os.path.join(output_dir, 'log', '{}.log'.format(hashed_url))
        image_logs_file = os.path.join(output_dir, 'log',
                                       '{}.img.log'.format(hashed_url))
        css_logs_file = os.path.join(output_dir, 'log',
                                     '{}.css.log'.format(hashed_url))
        screenshot_file = os.path.join(output_dir, 'screenshot',
                                       '{}.png'.format(hashed_url))

        # Read log contents
        text = html2text.html2text(html_file)
        logs = [json.loads(log) for log in
                      open(log_file).readlines()]
        image_logs = [json.loads(log) for log in
                      open(image_logs_file).readlines()]
        css_logs = [json.loads(log) for log in
                    open(css_logs_file).readlines()]

        # Calculate site damage
        damage = SiteDamage(text, logs, image_logs, css_logs, screenshot_file,
                            background_color)
        damage.calculate_all()

        result = {}
        result['uri'] = uri
        result['weight'] = {
            'multimedia' : damage.multimedia_weight,
            'css' : damage.css_weight,
            'image' : damage.image_weight,
            'text' : damage.text_weight
        }
        result['images'] = damage.image_logs
        result['csses'] = damage.css_logs
        result['potential_damage'] = {
            'total' : damage.potential_damage,
            'image' : damage.potential_image_damage,
            'css'   : damage.potential_css_damage,
            'text'  : damage.potential_damage_text,
        }
        result['actual_damage'] = {
            'total' : damage.actual_damage,
            'image' : damage.actual_image_damage,
            'css'   : damage.actual_css_damage,
            'text'  : damage.actual_damage_text,
        }
        result['total_damage'] = \
            damage.actual_damage/damage.potential_damage \
            if damage.potential_damage != 0 else 0

        print('Potential Damage : {}'.format(result['potential_damage']['total']))
        print('Actual Damage : {}'.format(result['actual_damage']['total']))
        print('Total Damage : {}'.format(result['total_damage']))
        print(json.dumps({'result' : result}))
