from platformdirs import user_log_path

import typer
from rich.console import Console
from loguru import logger
from datetime import datetime

LOG_DIR = user_log_path(appname="VibeCommit")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger(command_name: str, console: Console):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logfile = LOG_DIR / f"{command_name}_{timestamp}.log"

    # Clear existing sinks so we don't double-log across runs
    logger.remove()

    # Add console (info+) and file (debug+)
    logger.add(lambda msg: console.print(msg), level="INFO")
    logger.add(logfile, level="DEBUG", rotation="5 MB", retention="7 days")

    logger.info(f"Initialized logger for {command_name} → {logfile}")
    return logfile
