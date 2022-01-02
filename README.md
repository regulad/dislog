# DiscordWebhookLogger

Provides an interface for using a discord webhook as a logger.

## Example

```py
import dislog
import logging

logging.basicConfig(level=logging.ERROR, handlers=[dislog.DiscordWebhookHandler("url")])

logging.error("hi")
```

![img.png](img.png)
