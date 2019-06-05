import os
import sys
import json
import time
import logging
import operator
import calendar
import pandas as pd
import datetime as dt
import reporting.utils as utl
import selenium.webdriver as wd
import selenium.common.exceptions as ex


class RedApi(object):
    config_path = utl.config_path
    base_url = 'https://ads.reddit.com'
    temp_path = 'tmp'

    def __init__(self):
        self.browser = self.init_browser()
        self.base_window = self.browser.window_handles[0]
        self.config_file = None
        self.username = None
        self.password = None
        self.config_list = None
        self.config = None

    def input_config(self, config):
        logging.info('Loading Reddit config file: {}.'.format(config))
        self.config_file = os.path.join(self.config_path, config)
        self.load_config()
        self.check_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        except IOError:
            logging.error('{} not found.  Aborting.'.format(self.config_file))
            sys.exit(0)
        self.username = self.config['username']
        self.password = self.config['password']
        self.config_list = [self.username, self.password]

    def check_config(self):
        for item in self.config_list:
            if item == '':
                logging.warning('{} not in config file. '
                                ' Aborting.'.format(item))
                sys.exit(0)

    @staticmethod
    def get_data_default_check(sd, ed):
        if sd is None:
            sd = dt.datetime.today() - dt.timedelta(days=1)
        if ed is None:
            ed = dt.datetime.today() - dt.timedelta(days=1)
        return sd, ed

    @staticmethod
    def init_browser():
        download_path = os.path.join(os.getcwd(), 'tmp')
        co = wd.chrome.options.Options()
        co.add_argument('--disable-features=VizDisplayCompositor')
        prefs = {'download.default_directory': download_path}
        co.add_experimental_option('prefs', prefs)
        browser = wd.Chrome(options=co)
        browser.maximize_window()
        browser.set_script_timeout(10)
        return browser

    def go_to_url(self, url):
        logging.info('Going to url {}.'.format(url))
        try:
            self.browser.get(url)
        except ex.TimeoutException:
            logging.warning('Timeout exception, retrying.')
            self.go_to_url(url)
        time.sleep(5)

    def sign_in(self):
        logging.info('Signing in.')
        self.click_on_xpath('//*[@id="Content"]/h2/a')
        user_pass = [(self.username, '//*[@id="loginUsername"]'),
                     (self.password, '//*[@id="loginPassword"]')]
        for item in user_pass:
            elem = self.browser.find_element_by_xpath(item[1])
            elem.send_keys(item[0])
        login_xpaths = ['/html/body/div/div/div[2]/div/form/fieldset[5]/button']
        for xpath in login_xpaths:
            self.click_on_xpath(xpath, sleep=5)
        if self.browser.current_url != self.base_url:
            self.go_to_url(self.base_url)
        else:
            logo_xpath = '//*[@id="app"]/div/div[1]/div/a/img'
            self.click_on_xpath(logo_xpath, sleep=5)

    def click_on_xpath(self, xpath, sleep=2):
        self.browser.find_element_by_xpath(xpath).click()
        time.sleep(sleep)

    def set_breakdowns(self, base_xpath=None):
        logging.info('Setting breakdowns.')
        bd_xpath = 'div[3]/div[1]/div[1]/div/div[3]/div/div/div/div/div[1]'
        bd_xpath = base_xpath + bd_xpath
        self.click_on_xpath(bd_xpath)
        bd_date_xpath = '/html/body/div[6]/div/ul/li[1]'
        self.click_on_xpath(bd_date_xpath)

    def get_cal_month(self, lr=1, cal_xpath=None):
        month_xpath = '[2]/div[{}]/div[1]/div'.format(lr)
        cal_month_xpath = cal_xpath + month_xpath
        month = self.browser.find_element_by_xpath(cal_month_xpath).text
        month = dt.datetime.strptime(month, '%B %Y')
        if lr == 2:
            last_day = calendar.monthrange(month.year, month.month)[1]
            month = month.replace(day=last_day)
        return month

    @staticmethod
    def get_comparison(lr=1):
        if lr == 1:
            comp = operator.gt
        else:
            comp = operator.lt
        return comp

    def change_month(self, date, lr, cal_xpath, month):
        cal_sel_xpath = cal_xpath + '[1]/span[{}]'.format(lr)
        month_diff = abs((((month.year - date.year) * 12) +
                          month.month - date.month))
        for x in range(month_diff):
            self.click_on_xpath(cal_sel_xpath, sleep=1)

    def go_to_month(self, date, left_month, right_month, cal_xpath):
        if date < left_month:
            self.change_month(date, 1, cal_xpath, left_month)
        if date > right_month:
            self.change_month(date, 2, cal_xpath, right_month)

    def click_on_date(self, date):
        date = dt.datetime.strftime(date, '%a %b %d %Y')
        cal_date_xpath = "//div[@aria-label='{}']".format(date)
        self.click_on_xpath(cal_date_xpath)

    def find_and_click_date(self, date, left_month, right_month, cal_xpath):
        self.go_to_month(date, left_month, right_month, cal_xpath)
        self.click_on_date(date)

    def set_date(self, date, cal_xpath=None):
        cal_xpath = cal_xpath + '[1]/td[1]/div/div/div/div'
        left_month = self.get_cal_month(lr=1, cal_xpath=cal_xpath)
        right_month = self.get_cal_month(lr=2, cal_xpath=cal_xpath)
        self.find_and_click_date(date, left_month, right_month, cal_xpath)

    def open_calendar(self, base_xpath):
        cal_button_xpath = 'div[1]/div[2]/div/div'
        cal_xpath = base_xpath + cal_button_xpath
        self.click_on_xpath(cal_xpath)
        cal_table_xpath = '[2]/table/tbody/tr'
        cal_xpath = cal_xpath + cal_table_xpath
        return cal_xpath

    def set_dates(self, sd, ed, base_xpath=None):
        logging.info('Setting dates to {} and {}.'.format(sd, ed))
        cal_xpath = self.open_calendar(base_xpath)
        self.set_date(sd, cal_xpath=cal_xpath)
        self.set_date(ed, cal_xpath=cal_xpath)
        self.click_on_xpath(cal_xpath + '[2]/td/div/div/button[2]/span')

    def export_to_csv(self, base_xpath=None):
        logging.info('Downloading created report.')
        utl.dir_check(self.temp_path)
        export_xpath = base_xpath + 'div[1]/div[1]/div/div[3]/button'
        self.click_on_xpath(export_xpath)

    def create_report(self, sd, ed):
        logging.info('Creating report.')
        base_app_xpath = '//*[@id="app"]/div/div[2]/div[2]/'
        self.set_breakdowns(base_xpath=base_app_xpath)
        self.set_dates(sd, ed, base_xpath=base_app_xpath)
        self.export_to_csv(base_xpath=base_app_xpath)

    @staticmethod
    def get_file_as_df(temp_path=None):
        df = pd.DataFrame()
        for x in range(100):
            logging.info('Checking for file.  Attempt {}.'.format(x + 1))
            files = os.listdir(temp_path)
            if files:
                logging.info('File downloaded.')
                temp_file = os.path.join(temp_path, files[0])
                df = pd.read_csv(temp_file)
                os.remove(temp_file)
                break
            time.sleep(5)
        os.rmdir(temp_path)
        return df

    def get_data(self, sd=None, ed=None, fields=None):
        sd, ed = self.get_data_default_check(sd, ed)
        self.go_to_url(self.base_url)
        self.sign_in()
        self.create_report(sd, ed)
        df = self.get_file_as_df(self.temp_path)
        self.quit()
        return df

    def quit(self):
        self.browser.quit()