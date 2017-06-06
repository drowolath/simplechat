# simplechat

This is a simple chat engine based on Redis PubSub.
Each chat room is a Redis channel to which connected users subscribe.

When a message is published on the channel, all the subscribers receive it.
The publisher does not receive the same message.

There are currently 2 implemented interfaces (telnet and http) running separately.

## Installation

Currently tested only on GNU/Linux Debian Jessie

```
$ sudo apt-get install python-dev python-pip python-virtualenv
$ git clone https://github.com/drowolath/simplechat.git
$ virtualenv venv
$ source venv/bin/activate
(venv) $ cd simplechat
(venv)$ pip install -r requirements.txt
(venv)$ python setup.py sdist
(venv)$ pip install dist/simplechat-0.1.tar.gz
```

## Launch TCP socket server

```
(venv)$ simplechat runsocketserver
Listening on (0.0.0.0, 4242)
```

## Launch websocket server for http interface

```
(venv)$ gunicorn -k flask_sockets.worker simplechat:app -b 0.0.0.0:5000
```

## Telnet into it

```
$ telnet 127.0.0.1 4242
```


## via Web browser

If you have installed and launched the server locally, you can visit http://localhost:5000 .
