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

import sys
from logging import Logger

import pytest

from dislog import DiscordWebhookHandler


@pytest.fixture
def webhook_url() -> str:
    """
    Returns the webhook URL to use for testing.
    """
    return "https://discord.com/api/webhooks/1076589408138047599/7FPyX9qt5r-9Dck9w1sZMySKSonOCn0zHqEyuM9TzxNo-7AIuqym9WbAEKfUBfr51afE"
    # This is technically a secret, but it's not like anyone can do anything with it.


@pytest.fixture(scope="session")
def python_version_ident() -> str:
    """
    Returns the Python version to use for testing.
    """
    return ".".join(map(str, sys.version_info[:3]))


def get_logger(*args, **kwargs) -> Logger:
    """
    Returns a logger with a `dislog` name and the DiscordWebhookHandler attached with the given args and
    kwargs.
    """
    kwargs.setdefault("text_send_on_error", "<@440468612365680650>")

    handler = DiscordWebhookHandler(*args, **kwargs)
    logger = Logger("dislog")
    logger.addHandler(handler)
    return logger


__all__ = ("get_logger", "webhook_url", "python_version_ident")
