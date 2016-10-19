import contextlib
import os
import sys

import time
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.wait import WebDriverWait


class Crawler:
    def __init__(self, driver='http://127.0.0.1:4444/wd/hub',
                 capabilities=DesiredCapabilities.FIREFOX):
        # self.driver = webdriver.Chrome(os.path.join(os.path.dirname(__file__), 'chromedriver'))
        self.driver = webdriver.Remote(command_executor=driver,
                                       desired_capabilities=capabilities)

    def crawl(self, url):
        self.driver.get(url)

    @contextlib.contextmanager
    def wait_for_page_load(self, timeout=10):
        old_page = self.find_element_by_tag_name('html')
        yield
        WebDriverWait(self, timeout).until(staleness_of(old_page))

    def get_log(self):
        return self.driver.get_log('client')

    def take_screenshot(self, file):
        self.wait_for_page_load()
        self.driver.save_screenshot(file)

    def quit(self):
        self.driver.quit()


if __name__ == "__main__":
    # if len(sys.argv) > 0:
    #     if len(sys.argv) < 2:
    #         print('Usage :')
    #         print('python damage.py <uri> <cache_dir>')
    #         exit()
    #
    # Read arguments
    uri = 'http://acid3.acidtests.org/' #sys.argv[1]
    output_dir = '/home/soedomoto/selenium/' #sys.argv[2]

    crawler = Crawler(driver='http://172.17.0.5:4444/wd/hub')
    crawler.crawl(uri)
    crawler.take_screenshot(os.path.join(output_dir, 'ss.png'))
    crawler.quit()

