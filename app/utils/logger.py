import logging
import os
import sys


def setup_logger(
    name: str = __name__,
    log_path: str = "",
    level: str = "DEBUG",
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()

    level_names = logging.getLevelNamesMapping()
    level_value = level_names.get(level.upper())
    if isinstance(level_value, int) is False:
        raise TypeError(f"""Неизвестный уровень логирования: '{level}'
            Допустимые уровни: {list(level_names.keys())}""")

    logger.setLevel(level_value)  # pyright: ignore[reportArgumentType]

    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )

    if log_path:
        os.makedirs(log_path, exist_ok=True)
        log_file = os.path.join(log_path, "application.log")

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if log_path == "" or level == "DEBUG":
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
