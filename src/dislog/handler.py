"""
    DiscordWebhookLogger (dislog) provides an interface for using a Discord webhook as a logger.
    Copyright (C) 2022 Parker Wahle

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
from asyncio import get_running_loop, AbstractEventLoop
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from logging import LogRecord, Handler, NOTSET
from typing import List

from aiohttp import ClientSession
from discord import SyncWebhook, Webhook, Embed

DEPENDENCY_LOGGERS: set[str] = {
    "aiohttp",
    "discord",
    "asyncio",
    "concurrent.futures",
    "websockets",
    "urllib3",
}


def filter_out_dependencies(record: LogRecord) -> int:
    """
    Filters out records from dependencies. This is needed to not have an infinite loop of logging.
    """

    should_filter: bool = any(
        [record.name.startswith(dependency) for dependency in DEPENDENCY_LOGGERS]
    )

    return 0 if should_filter else 1


class DiscordWebhookHandler(Handler):
    """A logging handler that allows you to send messages with Discord Webhooks."""

    def __init__(
        self,
        webhook: str | SyncWebhook | Webhook,
        level: int = NOTSET,
        *,
        can_format: bool = False,
        run_async: bool = False,
    ) -> None:
        super().__init__(level)
        self.addFilter(filter_out_dependencies)

        self._format: bool = can_format
        self._async: bool = run_async
        self._webhook: SyncWebhook | Webhook

        self._aiohttp_session: ClientSession | None = None
        self._thread_pool: ThreadPoolExecutor | None = None

        if isinstance(webhook, str):
            if self._async:
                self._aiohttp_session = ClientSession()
                self._webhook = Webhook.from_url(webhook, session=self._aiohttp_session)
            else:
                self._webhook = SyncWebhook.from_url(webhook)
                self._thread_pool = ThreadPoolExecutor(
                    thread_name_prefix=f"dislog-{self._webhook.id}-"
                )

    def _send(self, *args, **kwargs) -> None:
        if self._async:
            assert (
                isinstance(self._webhook, Webhook) and self._aiohttp_session is not None
            )

            loop: AbstractEventLoop = get_running_loop()
            loop.create_task(self._webhook.send(*args, **kwargs))
            # note: this might not happen instantly. that's ok though, because we timestamp the message.
        else:
            assert (
                isinstance(self._webhook, SyncWebhook) and self._thread_pool is not None
            )

            self._thread_pool.submit(self._webhook.send, *args, **kwargs)

    def close(self) -> None:
        if self._async:
            assert self._aiohttp_session is not None
            loop: AbstractEventLoop = self._aiohttp_session.loop
            if loop.is_running():
                loop.create_task(self._aiohttp_session.close())
            elif not loop.is_closed():
                loop.run_until_complete(self._aiohttp_session.close())
            else:
                raise RuntimeWarning(
                    "The event loop is closed, so the aiohttp session cannot be closed."
                )
        else:
            assert self._thread_pool is not None
            self._thread_pool.shutdown()
        super().close()

    def emit(self, record: LogRecord) -> None:
        color: int
        if (
            record.levelname == "CRITICAL"
            or record.levelname == "FATAL"
            or record.levelname == "ERROR"
        ):
            color = 0xFF0000
        elif record.levelname == "WARN" or record.levelname == "WARNING":
            color = 0xFFFF00
        elif record.levelname == "DEBUG":
            color = 0x5A0D36  # picked from my oneshot banner because its eye-catching
        else:
            color = 0xFFFFFF

        embed_dict: dict = {
            "title": f"{record.levelname} on {record.threadName} ({record.thread})",
            "color": color,
            "description": f"```{self.format(record) if self._format else record.getMessage()}```",
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat(),
            "footer": {"text": record.name},
        }

        # patching over some legacy code here...

        embed: Embed = Embed.from_dict(embed_dict)

        self._send(embeds=[embed])


__all__: List[str] = ["DiscordWebhookHandler"]
