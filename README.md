# simplechat

This is a simple chat engine based on Redis PubSub.
Each chat room is a Redis channel to which connected users subscribe.

When a message is published on the channel, all the subscribers receive it.
The publisher does not receive the same message.

## Installation

```
$ pip install -r requirements.txt
$ python setup.py install
```

## Launch

```
$ simplechat
```

## Telnet

```
$ telnet 127.0.0.1 4242
```