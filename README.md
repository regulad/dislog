# [dislog](https://pypi.org/project/dislog/)

[![wakatime](https://wakatime.com/badge/github/regulad/dislog.svg)](https://wakatime.com/badge/github/regulad/dislog)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/regulad/dislog/ci.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/regulad/dislog/main.svg)](https://results.pre-commit.ci/latest/github/regulad/dislog/master)
![PyPI](https://img.shields.io/pypi/v/dislog)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dislog)

###### Previously [`discord-webhook-logger`](https://pypi.org/project/discord-webhook-logger/)

Provides an interface for using a Discord webhook as a logger.

Designed to abstract away webhook-specific details, such as the JSON format, and provide a simple interface for logging messages.

## Install

Simple as:

```sh
pip install dislog[discordpy]
```

You can use extras to define which implementation of `discord.py` you want to use.

* `discordpy`: `discord.py

## Example

Using `dislog` in your projects is dead simple. It behaves like any other `logging.Handler`.

For performance reasons, it even fires off a new thread for each log message, so you don't have to worry about blocking your main thread with costly HTTP requests.

```py
from dislog import DiscordWebhookHandler
from logging import *

basicConfig(level=ERROR, handlers=[StreamHandler(), DiscordWebhookHandler("url", text_send_on_error="<@440468612365680650>")])

error("hi")
```

![Demo](./Screenshot%202023-02-18%20154139.png)

It also works with asynchronous code, simply pass the `run_async` keyword argument. This is optional and makes it use the event loop instead of a thread pool.

```py
from dislog import DiscordWebhookHandler
from logging import *
from asyncio import run, sleep, get_running_loop

async def main():
    basicConfig(level=ERROR, handlers=[StreamHandler(), DiscordWebhookHandler("url", event_loop=get_running_loop(), text_send_on_error="<@440468612365680650>")])

    error("hi")

    await sleep(1)  # Give it some time to run!

run(main())
```

![Async Demo](./Screenshot%202023-02-18%20154119.png)

## Contributing

### Setup

```sh
git clone https://github.com/regulad/dislog
cd dislog
pip install -e .
pre-commit install
```

### Testing

```sh
tox
```
