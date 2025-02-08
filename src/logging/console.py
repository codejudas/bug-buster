import json
import logging
from typing import Optional, Dict, Any, List

import colored # type: ignore
from pydantic import BaseModel


class ConsoleFormatter(logging.Formatter):
    """
    Extends basic Python Formatter to print log lines to console in a nice way, ie with colors, and displaying the
    log metadata inline with the log message.
    """

    _COLOR_LVL_MAPPING = {
        logging.DEBUG: colored.fg("light_gray") + colored.attr("bold"),
        logging.INFO: colored.fg("white") + colored.attr("bold"),
        logging.WARNING: colored.fg("yellow") + colored.attr("bold"),
        logging.ERROR: colored.fg("red") + colored.attr("bold"),
        logging.FATAL: colored.fg("red") + colored.attr("bold"),
    }

    _STATUS_CODE_MAPPING = {
        200: colored.fg("green") + colored.attr("bold"),
        300: colored.fg("yellow") + colored.attr("bold"),
        400: colored.fg("orange_3") + colored.attr("bold"),
        500: colored.fg("red") + colored.attr("bold"),
    }

    def __init__(
        self,
        fmt: str,
        access_fmt: str,
        datefmt: Optional[str] = None,
        validate: bool = True,
        color: bool = True,
        truncate_meta: bool = False,
    ):
        super().__init__(fmt, datefmt, "{", validate)
        self.color = color
        self.access_fmt = access_fmt
        self.truncate_meta = truncate_meta

    def formatMessage(self, record: logging.LogRecord) -> str:
        """override"""
        return self.format_app_log(record)

    def formatException(self, ei) -> str:
        """override"""
        res = super().formatException(ei)
        return colored.stylize(res, colored.fg("dark_orange")) if self.color else res

    def format_access_log(self, record: logging.LogRecord) -> str:
        all_attrs = {**record.__dict__, **record.__dict__.get("msg", {})}

        # Colorize level
        if self.color and "levelname" in all_attrs:
            level_style = self._COLOR_LVL_MAPPING.get(record.levelno, self._COLOR_LVL_MAPPING[logging.INFO])
            all_attrs["levelname"] = colored.stylize(record.levelname, level_style)

        # Colorize name
        if self.color and "name" in all_attrs:
            all_attrs["name"] = colored.stylize(record.name, colored.fg("spring_green_2b"))

        # Colorize time
        if self.color and "asctime" in all_attrs:
            all_attrs["asctime"] = colored.stylize(record.asctime, colored.fg("grey_78") + colored.attr("bold"))

        # Colorize method
        if self.color and "method" in all_attrs:
            all_attrs["method"] = colored.stylize(all_attrs["method"], colored.fg("steel_blue") + colored.attr("bold"))

        # Colorize status code
        if self.color and "status" in all_attrs:
            status = all_attrs["status"]
            status_style = self._STATUS_CODE_MAPPING.get(status // 100 * 100, self._STATUS_CODE_MAPPING[400])
            all_attrs["status"] = colored.stylize(all_attrs["status"], status_style)

        return self.access_fmt.format(**all_attrs)

    def format_app_log(self, record: logging.LogRecord) -> str:
        overrides = {}

        # Colorize level
        if self.color and "levelname" in record.__dict__:
            level_style = self._COLOR_LVL_MAPPING.get(record.levelno, self._COLOR_LVL_MAPPING[logging.INFO])
            overrides["levelname"] = colored.stylize(record.levelname, level_style)

        # Colorize time
        if self.color and "asctime" in record.__dict__:
            overrides["asctime"] = colored.stylize(record.asctime, colored.fg("grey_78") + colored.attr("bold"))

        # Colorize name
        if self.color and "name" in record.__dict__:
            overrides["name"] = colored.stylize(record.name, colored.fg("blue"))

        # Colorize function name where log was emitted
        if self.color and "funcName" in record.__dict__:
            overrides["funcName"] = colored.stylize(record.funcName, colored.fg("blue"))

        # Colorize line number where log was emitted
        if self.color and "lineno" in record.__dict__:
            overrides["lineno"] = colored.stylize(str(record.lineno), colored.fg("yellow"))
        else:
            # Make this a string for consistency with the if statement above, otherwise formatting will fail
            overrides["lineno"] = str(record.lineno)

        # Add the logged meta as well to end of log line
        meta_str = self._format_meta(record.__dict__.get("metadata", {}), color=self.color)

        new_record = logging.makeLogRecord({**record.__dict__, **overrides})
        return super().formatMessage(new_record) + f" {meta_str}"

    def _format_meta(self, meta: Dict[str, Any], color=True) -> str:
        pieces = []
        for k in sorted(meta.keys()):
            v = meta[k]
            if isinstance(v, dict):
                try:
                    v = json.dumps(v)
                except Exception:
                    pass
            elif isinstance(v, BaseModel):
                v = v.model_dump_json()

            if color:
                k = colored.stylize(k, colored.fg("light_yellow"))
                v = colored.stylize(str(v), colored.fg("light_cyan"))

            pieces.append(f"{k}={v}")

        if self.truncate_meta and len(pieces) > 4:
            # Truncate it, we don't need all this info on the console output
            pieces = pieces[:2] + [colored.stylize("...", colored.fg("light_cyan")), pieces[-1]]

        joined = ", ".join(pieces)
        return f"[{joined}]" if joined else ""