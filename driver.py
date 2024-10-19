import os
import time
from log import Logger, LogLevel
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

class Driver(webdriver.Firefox):
    """
    Wrapper around Selenium webdriver
    """
    _profile = os.environ.get("MARIONETTE_PROFILE")

    def __init__(
            self,
            config: dict,
            logger: Logger
    ):
        self.logger = logger
        self._options = FirefoxOptions()
        self._options.add_argument("--profile")
        self._options.add_argument(str(self._profile))
        if config.get("headless"):
            self._options.add_argument("--headless")
        super().__init__(
            service=FirefoxService(GeckoDriverManager().install()), 
            options=self._options
        )
        self.implicitly_wait(config.get("driver_wait", 30))
        self.logger.log(f"Driver initialised with profile {self._profile}")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.quit()
    
    @staticmethod
    def sleep(secs: int):
        time.sleep(secs)
