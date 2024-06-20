import getpass
import logging
from functools import lru_cache
from pathlib import Path

import pytz as pytz
import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict
from structlog.typing import WrappedLogger, EventDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    BASE_DIR: Path = BASE_DIR
    TIMEZONE: str = "Europe/Moscow"
    HOST: str
    LOGIN: str
    PASSWORD: str
    # PASSWORD: str = getpass.getpass('Введите пароль: ')

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env")

    @property
    def tz(self):
        return pytz.timezone(self.TIMEZONE)


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
tz = pytz.timezone(settings.TIMEZONE)


def get_my_loggers():
    class LogJump:
        def __init__(
            self,
            full_path: bool = False,
        ) -> None:
            self.full_path = full_path

        def __call__(
            self, logger: WrappedLogger, name: str, event_dict: EventDict
        ) -> EventDict:
            if self.full_path:
                file_part = "\n" + event_dict.pop("pathname")
            else:
                file_part = event_dict.pop("filename")
            event_dict["location"] = f'"{file_part}:{event_dict.pop("lineno")}"'

            return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.processors.CallsiteParameterAdder(
                [
                    # add either pathname or filename and then set full_path to True or False in LogJump below
                    # structlog.processors.CallsiteParameter.PATHNAME,
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ],
            ),
            LogJump(full_path=False),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        # logger_factory=structlog.WriteLoggerFactory(file=Path("logs/bot").with_suffix(".log").open("wt")),
        cache_logger_on_first_use=False,
    )
    return structlog.stdlib.get_logger()


logger = get_my_loggers()
logger.info(str(settings))


press_home = 'input keyevent 3'
press_tab = 'input keyevent 61'