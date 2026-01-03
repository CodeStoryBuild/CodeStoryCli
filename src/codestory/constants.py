# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

from pathlib import Path

from platformdirs import user_config_dir, user_log_path

APP_NAME = "codestory"
ENV_APP_PREFIX = APP_NAME.upper()
LOG_DIR = Path(user_log_path(appname=APP_NAME))

ONBOARDING_FLAG = Path(user_config_dir(APP_NAME)) / "onboarding_flag"

CONFIG_FILENAME = "codestoryconfig.toml"

GLOBAL_CONFIG_FILE = Path(user_config_dir(APP_NAME)) / CONFIG_FILENAME
LOCAL_CONFIG_FILE = Path(CONFIG_FILENAME)
