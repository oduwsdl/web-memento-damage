from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options, DesiredCapabilities

options = Options()
options.add_argument("user-data-dir=./data");
options.add_argument("start-maximized");

desired_capabilities = DesiredCapabilities.CHROME.copy()

driver = webdriver.Chrome(chrome_options=options,
                          desired_capabilities=desired_capabilities)
driver.get("http://www.python.org")

script = "var performance = window.performance || window.mozPerformance || window.msPerformance || window.webkitPerformance || {}; var network = performance.getEntries() || {}; return network;";
net_data = driver.execute_script(script)
print(net_data)

driver.close()
