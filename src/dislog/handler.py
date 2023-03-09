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
from asyncio import get_running_loop, AbstractEventLoop, Queue as AsyncioQueue
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from logging import LogRecord, Handler, NOTSET, ERROR
from typing import List, Awaitable

from aiohttp import ClientSession
from discord import SyncWebhook, Webhook, Embed, Message
from discord.utils import MISSING

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

    should_filter: bool = any([record.name.startswith(dependency) for dependency in DEPENDENCY_LOGGERS])

    return 0 if should_filter else 1


def loop_or_none() -> AbstractEventLoop | None:
    """
    Gets the current running loop, or None if there is no running loop.
    """

    try:
        return get_running_loop()
    except RuntimeError:
        return None


class DiscordWebhookHandler(Handler):
    """A logging handler that allows you to send messages with Discord Webhooks."""

    def __init__(
        self,
        webhook: str | SyncWebhook | Webhook,
        level: int = NOTSET,
        *,
        can_format: bool = False,
        event_loop: AbstractEventLoop | None = None,
        text_send_on_error: str | None = None,
        text_send_on_error_threshold: int = ERROR,
    ) -> None:
        """
        :param webhook: The webhook to send messages to.
        :param level: The level to log at.
        :param can_format: Whether to format the message using the formatter, or to just send it in the Discord
        description.
        :param event_loop: The event loop to use. If this is None, then no event loop will be used, and a thread will instead
        be used to send messages. This is useful if you are using a synchronous Discord library. Download the `sync`
        extra to use this without extra dependency handling.
        :param text_send_on_error: The text to send if an error occurs while sending a message. If this is None, then
        no text will be sent on error. This is useful to send stuff like a mention (<@440468612365680650>).
        :param text_send_on_error_threshold: The level at which to send the text on error. Defaults to logging.ERROR.
        """
        super().__init__(level)

        self.addFilter(filter_out_dependencies)  # type: ignore  # mypy doesn't like this

        self._format: bool = can_format
        self._async: bool = event_loop is not None and isinstance(event_loop, AbstractEventLoop)

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

        self._runner: AbstractEventLoop | ThreadPoolExecutor
        self._queue: AsyncioQueue[tuple[LogRecord | None, Awaitable[Message]]] | None = None
        if event_loop is not None:
            self._runner = event_loop
            self._queue = AsyncioQueue()
        else:
            self._runner = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dislog")

        self._text_send_on_error = text_send_on_error
        self._text_send_on_error_threshold = text_send_on_error_threshold

    async def _async_consume(self) -> None:
        assert isinstance(self._queue, AsyncioQueue), "Queue is not an asyncio.Queue!"

        record, coro = await self._queue.get()
        try:
            await coro
        except Exception:  # noqa
            if record is not None:
                self.handleError(record)
        finally:
            self._queue.task_done()

    def _send(self, record: LogRecord | None, *args, **kwargs) -> None:
        send_partial = partial(self._webhook.send, *args, **kwargs)
        if self._async:
            assert isinstance(self._runner, AbstractEventLoop), "Runner is not an event loop!"
            assert isinstance(self._webhook, Webhook), "Webhook is not a discord.Webhook"
            assert isinstance(self._queue, AsyncioQueue), "Queue is not an asyncio.Queue!"

            send_coro: Awaitable[Message] = send_partial()  # type: ignore  # mypy doesn't like this
            tup = (record, send_coro)
            self._queue.put_nowait(tup)

            consume_coro = self._async_consume()

            # This needs to be a callback so that the shield runs on the same thread as the EventLoop
            self._runner.call_soon_threadsafe(partial(asyncio.shield, consume_coro))
        else:
            assert isinstance(self._runner, ThreadPoolExecutor), "Runner is not a thread pool!"
            assert isinstance(self._webhook, SyncWebhook), "Webhook is not a discord.SyncWebhook"

            self._runner.submit(send_partial)

    def _close_sync(self) -> None:
        assert isinstance(self._runner, ThreadPoolExecutor), "Runner is not a thread pool!"
        assert isinstance(self._webhook, SyncWebhook), "Webhook is not a discord.SyncWebhook"

        self._runner.shutdown(wait=True)

    async def _close_async(self) -> None:
        assert isinstance(self._queue, AsyncioQueue), "Queue is not an asyncio.Queue"
        assert isinstance(self._webhook, Webhook), "Webhook is not a discord.Webhook"
        assert self._aiohttp_session is not None, "Session is None"

        await self._queue.join()  # noqa  # pycharm is wrong
        await self._aiohttp_session.close()

    def close(self) -> None:
        self._send(None, "**CLOSED**")
        if self._async:
            assert isinstance(self._runner, AbstractEventLoop), "Runner is not an event loop!"
            assert isinstance(self._webhook, Webhook), "Webhook is not a discord.Webhook"
            assert self._aiohttp_session is not None, "Session is None"

            cancel_task = self._runner.create_task(self._close_async())

            if self._runner.is_closed():
                raise RuntimeError("Event loop is closed, cannot close handler!")

            running_loop = loop_or_none()
            if not self._runner.is_running():
                # The loop isn't running, but it's not closed.
                self._runner.run_until_complete(cancel_task)
            elif running_loop is self._runner:
                # The loop is running, and it's the current loop.
                # There is nothing we can do that will not deadlock.
                pass
            elif running_loop is None:
                # The loop is running, but it's not the current loop.
                concurrent_future = asyncio.run_coroutine_threadsafe(cancel_task, self._runner)
                concurrent_future.result()  # We can wait.
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

        content: str | MISSING = MISSING
        if (
            self._text_send_on_error_threshold <= record.levelno
            and self._text_send_on_error is not None
            and len(self._text_send_on_error) > 0
        ):
            content = self._text_send_on_error

        self._send(record, embed=embed, content=content)


__all__: List[str] = ["DiscordWebhookHandler"]
