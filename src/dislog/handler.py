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

from asyncio import get_running_loop, AbstractEventLoop, Queue as AsyncioQueue
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from logging import LogRecord, Handler, NOTSET, ERROR
from queue import Queue
from threading import Thread, Event
from typing import List, Any

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


class DiscordWebhookHandler(Handler, Thread):  # type: ignore  # not a catostrophic clash of DiscordWebhookHandler.name
    """A logging handler that allows you to send messages with Discord Webhooks."""

    def __init__(
        self,
        webhook: str | SyncWebhook | Webhook,
        level: int = NOTSET,
        *,
        can_format: bool = False,
        run_async: bool = False,
        text_send_on_error: str | None = None,
        text_send_on_error_threshold: int = ERROR,
    ) -> None:
        """
        :param webhook: The webhook to send messages to.
        :param level: The level to log at.
        :param can_format: Whether to format the message using the formatter, or to just send it in the Discord
        description.
        :param run_async: Whether to run the webhook in an async context. This is useful if your app is async. If your
        app isn't async (it is using threading or another concurrency method not based on asyncio), then you should
        install the `sync` extra or install your own version of `requests`.
        :param text_send_on_error: The text to send if an error occurs while sending a message. If this is None, then
        no text will be sent on error. This is useful to send stuff like a mention (<@440468612365680650>).
        :param text_send_on_error_threshold: The level at which to send the text on error. Defaults to logging.ERROR.
        """
        Handler.__init__(self, level)

        self.addFilter(filter_out_dependencies)

        self._format: bool = can_format
        self._async: bool = run_async

        self._aiohttp_session: ClientSession | None = None

        self._webhook: SyncWebhook | Webhook
        if isinstance(webhook, str):
            if self._async:
                self._aiohttp_session = ClientSession()
                self._webhook = Webhook.from_url(webhook, session=self._aiohttp_session)
            else:
                self._webhook = SyncWebhook.from_url(webhook)
        elif isinstance(webhook, SyncWebhook):
            self._webhook = webhook
        elif isinstance(webhook, Webhook):
            self._webhook = webhook
            self._aiohttp_session = webhook.session

        self._queue: AsyncioQueue[tuple[tuple[Any, ...], dict[str, Any]]] | Queue[
            tuple[tuple[Any, ...], dict[str, Any]]
        ]
        self._shutdown_event: Event | None = None
        if self._async:
            self._queue = AsyncioQueue()
        else:
            self._queue = Queue()
            self._shutdown_event = Event()
            Thread.__init__(self, name=self.name, daemon=True)
            self.start()

        self._text_send_on_error = text_send_on_error
        self._text_send_on_error_threshold = text_send_on_error_threshold

    def run(self) -> None:
        assert not self._async, "Cannot run a thread in an async context."

        assert self._shutdown_event is not None, "Shutdown event is None"
        assert isinstance(self._queue, Queue), "Queue is not a queue.Queue"

        while not self._shutdown_event.is_set() or not self._queue.empty():
            args, kwargs = self._queue.get()
            self._webhook.send(*args, **kwargs)
            self._queue.task_done()

    async def _send_one_async(self) -> None:
        assert isinstance(self._queue, AsyncioQueue), "Queue is not an asyncio.Queue"
        assert isinstance(self._webhook, Webhook), "Webhook is not a discord.Webhook"

        args, kwargs = self._queue.get_nowait()
        await self._webhook.send(*args, **kwargs)

    def _send(self, *args, **kwargs) -> None:
        self._queue.put_nowait((args, kwargs))
        if self._async:
            assert self._aiohttp_session is not None, "Session is None"
            loop: AbstractEventLoop
            if (
                getattr(self._aiohttp_session, "loop", None) is None
            ):  # loop is deprecated
                loop = get_running_loop()
            else:
                loop = self._aiohttp_session.loop

            loop.create_task(self._send_one_async())
            # note: this might not happen instantly. that's ok though, because we timestamp the message.

    def _close_sync(self) -> None:
        assert isinstance(self._queue, Queue), "Queue is not a queue.Queue"
        assert self._shutdown_event is not None, "Shutdown event is None"
        assert isinstance(
            self._webhook, SyncWebhook
        ), "Webhook is not a discord.SyncWebhook"

        self._shutdown_event.set()
        self._send("**CLOSED**")
        self._queue.join()

    async def _close_async(self) -> None:
        assert isinstance(self._queue, AsyncioQueue), "Queue is not an asyncio.Queue"
        assert isinstance(self._webhook, Webhook), "Webhook is not a discord.Webhook"
        assert self._aiohttp_session is not None, "Session is None"

        self._send("**CLOSED**")
        await self._queue.join()  # noqa  # pycharm is wrong
        await self._aiohttp_session.close()

    def close(self) -> None:
        if self._async:
            assert isinstance(
                self._queue, AsyncioQueue
            ), "Queue is not an asyncio.Queue"
            assert isinstance(
                self._webhook, Webhook
            ), "Webhook is not a discord.Webhook"

            assert self._aiohttp_session is not None, "Session is None"
            loop: AbstractEventLoop
            if (
                getattr(self._aiohttp_session, "loop", None) is None
            ):  # loop is deprecated
                loop = get_running_loop()
            else:
                loop = self._aiohttp_session.loop

            if loop.is_running():
                loop.create_task(self._close_async())
            elif not loop.is_closed():
                loop.run_until_complete(self._close_async())
            else:
                raise RuntimeError("Cannot run async without an event loop candidate!")
        else:
            self._close_sync()
        super().close()

    def emit(self, record: LogRecord) -> None:
        color: int
        if record.levelno >= 40:
            color = 0xFF0000
        elif record.levelno >= 30:
            color = 0xFFFF00
        elif record.levelname == "DEBUG":  # debug is a special case
            color = 0x5A0D36  # picked from my oneshot banner because its eye-catching
        else:
            color = 0xFFFFFF

        # patching over some legacy code here...

        embed = Embed.from_dict(
            {
                "title": f"{record.levelname} on {record.threadName} ({record.thread})",
                "color": color,
                "description": f"```{self.format(record) if self._format else record.getMessage()}```",
                "timestamp": datetime.utcfromtimestamp(record.created).isoformat(),
                "footer": {"text": record.name},
            }
        )

        if (
            self._text_send_on_error_threshold <= record.levelno
            and self._text_send_on_error is not None
            and len(self._text_send_on_error) > 0
        ):
            self._send(self._text_send_on_error, embeds=[embed])
        else:
            self._send(embeds=[embed])


__all__: List[str] = ["DiscordWebhookHandler"]
