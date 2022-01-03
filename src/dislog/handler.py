import datetime
from logging import LogRecord, Handler, NOTSET
from typing import Optional, List

from requests import Session


class DiscordWebhookHandler(Handler):
    def __init__(
            self,
            webhook: str,
            level: int = NOTSET,
            *,
            session: Optional[Session] = None,
            format: bool = False,
    ):
        super().__init__(level)
        self._webhook: str = webhook
        self._new_client: bool = session is None
        self._session: Session = session or Session()
        self._format: bool = format

    def close(self) -> None:
        self._session.post(self._webhook, json={
            "content": "**CLOSED**"
        })
        if self._new_client:
            self._session.close()

    def emit(self, record: LogRecord) -> None:
        if record.levelname == "CRITICAL" or record.levelname == "FATAL" or record.levelname == "ERROR":
            color: int = 0xFF0000
        elif record.levelname == "WARN" or record.levelname == "WARNING":
            color: int = 0xFFFF00
        elif record.levelname == "DEBUG":
            color: int = 0x5a0d36  # picked from my oneshot banner because its eye-catching
        else:
            color: int = 0xFFFFFF

        self._session.post(self._webhook, json={
            "embeds": [
                {
                    "title": f"{record.levelname} on {record.threadName} ({record.thread})",
                    "color": color,
                    "description": f"```{self.format(record) if self._format else record.getMessage()}```",
                    "timestamp": datetime.datetime.utcfromtimestamp(record.created).isoformat(),
                    "footer": {
                        "text": record.name
                    }
                }
            ]
        })


__all__: List[str] = [
    "DiscordWebhookHandler"
]
