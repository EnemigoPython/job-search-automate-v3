import os
import time
from log import Logger, LogLevel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager

class Driver(webdriver.Firefox):
    """
    Wrapper around Selenium webdriver
    """
    _by = By  # silence not accessed - `By` is re-imported
    _profile = os.environ.get("MARIONETTE_PROFILE")
    class Exceptions:
        """
        Re-import selenium errors from a convenient interface
        """
        NOT_FOUND = NoSuchElementException
        TIMEOUT = TimeoutException
    
    class Condition:
        """
        Re-import selenium Expected Conditions (EC) from a convenient interface
        """
        ELEMENT_FOUND = EC.presence_of_element_located
        ELEMENT_CLICKABLE = EC.element_to_be_clickable
        ELEMENT_VISIBLE = EC.visibility_of

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
        self._wait = config.get("driver_wait", 30)
        self.implicitly_wait(self._wait)
        self.logger.log(f"Driver initialised with profile {self._profile}")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.logger.log("Exiting driver")
        self.quit()
    
    @staticmethod
    def sleep(secs: int):
        time.sleep(secs)

    def wait_until(
            self, 
            condition: callable, 
            args: tuple, 
            wait:int|None=None, 
            can_fail=True
        ):
        """
        Use an expected condition (EC) to pause the driver until the condition is met or timeout
        """
        assert hasattr(EC, condition.__name__), \
            f"Not a valid option for condition: '{condition.__name__}'"
        _wait = wait or self._wait
        try:
            WebDriverWait(self, _wait).until(condition(args))
            return True
        except TimeoutException:
            if can_fail:
                return False
            raise TimeoutException
