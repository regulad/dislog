"""
    DiscordWebhookLogger (dislog) provides an interface for using a Discord webhook as a logger.
    Copyright (C) 2023 Parker Wahle

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
from __future__ import annotations

import asyncio
from asyncio import sleep

import pytest

from . import *


@pytest.mark.asyncio
async def test_async_handler(webhook_url: str, python_version_ident: str) -> None:
    """
    Tests the handler running in asynchronous mode (asyncio).
    """
    loop = asyncio.get_event_loop()
    logger = get_logger(webhook_url, event_loop=loop)

    logger.exception(f"Async Exception on {python_version_ident}!")
    logger.critical(f"Async Critical on {python_version_ident}!")
    logger.error(f"Async Error on {python_version_ident}!")
    logger.warning(f"Async Warning on {python_version_ident}!")
    logger.info(f"Async Info on {python_version_ident}!")
    logger.debug(f"Async Debug on {python_version_ident}!")
    # Output must be manually validated.

    for handler in logger.handlers.copy():
        logger.removeHandler(handler)
        handler.close()

    await sleep(5)  # In async mode, we need a little time to finish sending the messages.


__all__ = ("test_async_handler",)
