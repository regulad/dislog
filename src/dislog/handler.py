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
    ):
        super().__init__(level)
        self._webhook: str = webhook
        self._session: Session = session or Session()

    def emit(self, record: LogRecord) -> None:
        if record.levelname == "CRITICAL" or record.levelname == "FATAL" or record.levelname == "ERROR":
            color: int = 0xFF0000
        elif record.levelname == "WARN" or record.levelname == "WARNING":
            color: int = 0xFFFF00
        else:
            color: int = 0xFFFFFF

        self._session.post(self._webhook, json={
            "embeds": [
                {
                    "title": f"{record.levelname} on {record.threadName}",
                    "color": color,
                    "description": f"```{record.getMessage()}```",
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
