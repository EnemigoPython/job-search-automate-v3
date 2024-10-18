from pathlib import Path
from enum import Enum
import traceback
import logging
import sys
from art import text2art


class LogLevel(Enum):
    """Derivation of levels from the logging module"""
    INFO = 20
    WARNING = 30
    ERROR = 40

class Logger:
    def __init__(self, path: str):
        self._configure_logger(path)
        self._log(text2art("Logger Online!"))
        self._log(""""Yeah, but Anton doesn't call me anything. He grimly does his work, then he sits motionless until it's time to work again. We could all take a page from his book." """)
    
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if any(exc):
            # we get the name of an exception with e.__class__.__name__, but exc[0] is not of type Exception
            self._log(f"Script crashed with a {repr(exc[0].__name__)}: view traceback below", LogLevel.ERROR)
            self._log(traceback.format_exc(), LogLevel.ERROR)
        else:
            self._log("Script ran to completion: exiting\n")
        self._logger.handlers.clear()

    def log(self, msg: str, level=LogLevel.INFO):
        """External interface to call the logger with the caller filename"""
        caller = Path(traceback.extract_stack()[-2].filename).name
        self._log_fn_dict[level](msg, extra={"_filename": caller})

    def _log(self, msg: str, level=LogLevel.INFO, verbose=False):
        """Internal version of log with filename set to this file"""
        if not verbose or self._verbose_log:
            self._log_fn_dict[level](msg, extra={"_filename": "log.py"})

    def _configure_logger(self, path):
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.StreamHandler(sys.stdout))
        self._logger.addHandler(logging.FileHandler(path))
        self._logger.setLevel(logging.INFO)
        for handler in self._logger.handlers:
            handler.setFormatter(logging.Formatter("[%(_filename)s %(asctime)s] %(levelname)s: %(message)s"))
        self._log_fn_dict = {
            LogLevel.INFO: self._logger.info,
            LogLevel.WARNING: self._logger.warning,
            LogLevel.ERROR: self._logger.error
        }
