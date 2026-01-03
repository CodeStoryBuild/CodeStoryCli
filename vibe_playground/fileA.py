from pathlib import Path
from pydantic import BaseModel, TypeAdapter
import tomli
import os
from vibe.core.config.config_loader import ConfigLoader
from loguru import logger

logger.remove()
logger.add(lambda message: print(message), level="DEBUG")

class Test(BaseModel):
    a: int = 2
    b: int
    c: int
    d: int = 4


os.environ["TEST_c"] = "2"


config, used_sources = ConfigLoader.get_full_config(Test, {"a": 99}, Path(".vibeconfig.toml"), "TEST_", Path(".vibeconfig2.toml"), Path(".vibeconfig3.toml"))
print(f"{config=}\n{used_sources=}")