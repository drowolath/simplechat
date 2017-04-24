#!/usr/bin/env python
# encoding: utf-8

"""
Simple chat server with a backend built with Redis PubSub.
Each chatroom is backed up by a Redis channel to which
users are subscribed.

By default, every new user is subscribed to the 'default' pubsub.
Every message is stored as a dictionnary with 'name' and 'text'
as keys holding data.

There are two interfaces: telnet and websockets, they are isolated.
"""

import gevent
import json
import os
import redis
import socket
import string
import thread
import time
from flask import Flask, redirect, render_template, request, session, url_for
from flask_sockets import Sockets
from flask_script import Manager



REDIS_URL = os.environ.get('REDIS_URL', '127.0.0.1:6379')
USERS = {}
ROOMS = []

redis_server = redis.from_url(REDIS_URL)
app = Flask(__name__)
app.secret_key = 'keep it secret'
app.debug = 'DEBUG'
websocketserver = Sockets(app)
manager = Manager(app)


class User(object):
    
    def __init__(self, name, connection=None, room=None, telnet=None):
        self.name = name
        self.connection = connection
        self.room = room
        self.telnet = telnet
        USERS[name] = self


class Backend(object):
    """backend for simple chat based on redis PubSub"""

    def __init__(self, name=None):
        self.name = name or 'default'
        self.users = dict()
        self.pubsub = redis_server.pubsub()
        self.pubsub.subscribe(self.name)

    def __str__(self):
        return '<ChatRoom {0}>'.format(self.name)

    def __unpack__(self):
        """Yield out data from pubsub"""
        for item in self.pubsub.listen():
            message = item.get('data')
            if item['type'] == 'message':
                yield message

    def register(self, user):
        """Register a user"""
        self.users[user.name] = user
        user.room = self
        redis_server.publish(
            self.name,
            json.dumps({
                'name': 'simplechat',
                'text': '{0} joined the chat'.format(user.name)
                })
            )

    def remove(self, user):
        """Remove a user"""
        if self.name != 'default':
            redis_server.publish(
                self.name,
                json.dumps({
                    'name': 'simplechat',
                    'text': '{0} left the room'.format(user.name)
                    })
            )
        del self.users[user.name]

    def parse(self, data):
        """Parsing messages"""
        payload = json.loads(data)
        name = payload['name']
        message = payload['text']
        user = self.users[name]
        if self.name == 'default':  # commands available in default        
            if message.startswith('/join'):
                new_room = message.split('/join ')[1]
                if user.telnet:
                    new_room = 'telnet.{0}'.format(new_room)
                room = [i for i in ROOMS if i.name == new_room]
                if not room:
                    room = Backend(new_room)
                    ROOMS.append(room)
                    room.start()
                else:
                    room = room[0]
                message = [
                    'Entering room: {0}'.format(room.name),
                    'Active users are:{0}'.format(
                        '\n'.join(['* {0}'.format(i) for i in room.users])),
                    '* {0} (** this is you)'.format(user.name),
                    'End of list'
                    ]
                room.register(user)
                self.remove(user)
            elif message == '/users':
                users = list()
                for i in USERS:
                    if i == user.name:
                        users.append('* {0} (**this is you)'.format(i))
                    else:
                        users.append('* {0}'.format(i))
                message = [
                    'Connected users are:',
                    '\n'.join(users),
                    'End of list'
                    ]
            elif message == '/rooms':
                rooms = [
                    i for i in ROOMS
                    if i.name != 'default' and i.startswith('telnet.')
                    ]
                if rooms:
                    message = [
                        'Active rooms are:',
                        '\n'.join(['* {0} ({1})'.format(
                            i.name, len(i.users)
                            ) for i in rooms]),
                        'End of list'
                        ]
                else:
                    message = ['No active room detected. Create one']
            elif message == '/quit':
                self.remove(user)
                message = ['BYE']
                del USERS[user.name]
                redis_server.srem('users', user.name)
            else:
                message = ['Sorry, unknown command or wrong domain']
        elif message == '/leave':
            room = filter(lambda x: x.name=='default', ROOMS)[0]
            room.register(user)
            self.remove(user)
            message = ['Leaving room {0}'.format(self.name)]
        else:
            message = ['Sorry, unknown command or wrong domain']
        return {'name': 'simplechat', 'text': '\n'.join(message)}
        
    def send(self, user, data):
        """Send data to registered user. Delete on failure"""
        payload = json.loads(data)
        name = payload['name']
        message = payload['text']
        null_data = (
            (message.startswith('/') and user.name != name) or
            (message == '{0} joined the chat'.format(user.name)) or
            (message == '{0} left the room'.format(user.name))
            )
        if message.startswith('/') and user.name == name:
            payload = self.parse(data)
        elif self.name == 'default' and user.name == name:
            payload = {
                'name': 'simplechat',
                'text': 'Please, join a room to start a discussion'
                }
        elif null_data:
            payload = None

        if payload:
            try:
                if user.room.name != self.name:
                    user.room.send(user, json.dumps(payload))
                else:
                    if user.telnet:
                        if payload['name'] == 'simplechat':
                            data = '<= {0}\n=> '.format(
                                payload['text'].replace('\n', '\n=> ')
                                )
                        else:
                            data = '<= ({0}) {1}'.format(payload['text'])
                    else:
                        data = json.dumps(payload)
                    user.connection.send(data)
            except Exception as exc:  # directly discard on conn failure
                self.remove(user)
            
    def run(self):
        """Listen and send messages"""
        for data in self.__unpack__():
            for _, user in self.users.items():
                thread.start_new_thread(self.send, (user, data))

    def start(self):
        thread.start_new_thread(self.run, ())


default = Backend()
ROOMS.append(default)
default.start()

        
@app.route('/')
def index():
    if 'username' in session:
        username = session['username']
        if not USERS:
            return redirect(url_for('logout'))
        return render_template('index.html', username=username)
    return redirect(url_for('register'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        if username and not username in USERS:
            User(username, room=default)
            session['username'] = request.form['username']
            return redirect(url_for('index'))
        elif not username or username[0] not in string.letters + string.digits:
            error = 'Invalid user name'
        elif username in USERS:
            error = 'User name already taken'
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.clear()
    return redirect(url_for('index'))

@websocketserver.route('/submit')
def inbox(ws):
    """Receives incoming chat messages, inserts them into Redis."""
    username = session['username']
    user = USERS[username]
    while not ws.closed:
        # Sleep to prevent *constant* context-switches.
        gevent.sleep(0.1)
        message = ws.receive()
        if message:
            redis_server.publish(user.room.name, message)

@websocketserver.route('/receive')
def outbox(ws):
    """Sends outgoing chat messages"""
    username = session['username']
    user = USERS[username]
    user.connection = ws
    user.room.register(user)
    while not ws.closed:
        # Context switch while `ChatBackend.start` is running in the background.
        gevent.sleep(0.1)

        
class SocketServer(object):
    """Simple TCP socket server"""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(False)
        self.socket.bind((self.host, self.port))
        self.socket.listen(1)
        print 'Listening on {0}'.format(self.socket.getsockname())

    def accept(self):
        """Continuously accept inbound connections"""
        def inner_thread(client):
            while True:
                client.send('<= Login name?\n=> ')
                try:
                    name = client.recv(1024).strip()  # no trailing spaces
                except socket.error:
                    continue
                if name in USERS:
                    client.send('<= Sorry, username already taken\n')
                elif not name or name[0] not in string.letters + string.digits:
                    client.send('<= Invalid username\n')
                else:
                    client.setblocking(False)
                    client.send('<= Welcome {0}\n=> '.format(name))
                    user = User(
                        name, room=default, connection=client, telnet=True
                        )
                    default.register(user)
                    break
                    
        while True:
            try:
                client, address = self.socket.accept()
            except socket.error:
                break
            msgs = [
                'Welcome to the simplechat chat server',
                '/users : gives you the list of connected users',
                '/rooms: gives you the list of available rooms',
                '/join room_name: allows you to join conversation in a room',
                '/leave: let you leave the room',
                '/quit: disconnects you from the server'
                ]
            for msg in msgs:
                client.send('<= {0}\n'.format(msg))
            thread.start_new_thread(inner_thread, (client,))

    def recv(self):
        """Continuously accept incoming messages"""
        for _, user in USERS.items():
            try:
                message = user.connection.recv(1024).strip()
                data = json.dumps({'name': user.name, 'text': message})
            except socket.error:
                continue
            redis_server.publish(user.room.name, data)
            user.connection.send('=> ')
            time.sleep(.1)

    def run(self):
        """Main routine to launch the server"""
        while True:
            try:
                self.accept()
                self.recv()
            except (KeyboardInterrupt, SystemExit):
                print 'Closing server'
                break


@manager.option('-H', '--host', dest='host')
@manager.option('-p', '--port', dest='port')
def runsocketserver(host=None, port=None):
    host = host or '0.0.0.0'
    port = port or 4242
    server = SocketServer(host, int(port))
    server.run()


if __name__ == '__main__':
    manager.run()
# EOF
