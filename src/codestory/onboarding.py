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

import typer
from colorama import Fore, Style

from codestory.commands.config import set_config
from codestory.constants import ONBOARDING_FLAG


def run_onboarding():
    print(f"{Fore.WHITE}{Style.BRIGHT}Welcome to codestory!{Style.RESET_ALL}")
    print(
        f"{Fore.WHITE}{Style.BRIGHT}This is the first time you're running codestory. Let's get started!{Style.RESET_ALL}"
    )
    print(
        f"{Fore.WHITE}{Style.BRIGHT}You'll be asked a few questions to configure codestory.{Style.RESET_ALL}"
    )
    print(
        f"{Fore.WHITE}{Style.BRIGHT}You can always change these settings later using the 'config' command.{Style.RESET_ALL}"
    )
    print(f"{Fore.WHITE}{Style.BRIGHT}Press Enter to continue.{Style.RESET_ALL}")
    input()
    model = typer.prompt(
        "What AI model would you like to use? Format=provider:model (e.g., openai:gpt-4)"
    )
    api_key = typer.prompt("What is your API key?")
    global_ = typer.confirm(
        "Do you want to set this as the global configuration?", default=False
    )
    set_config(key="model", value=model, scope="global" if global_ else "local")
    set_config(key="api_key", value=api_key, scope="global" if global_ else "local")
    print(f"{Fore.WHITE}{Style.BRIGHT}Configuration completed!{Style.RESET_ALL}")
    print(
        f"{Fore.WHITE}{Style.BRIGHT}You can always change these settings and more later using the 'config' command.{Style.RESET_ALL}"
    )

    return


def check_run_onboarding(exit_after: bool = True) -> None:
    # check a file in user config dir
    if not ONBOARDING_FLAG.exists():
        run_onboarding()
        ONBOARDING_FLAG.touch()
        if exit_after:
            raise typer.Exit(0)
    else:
        return
