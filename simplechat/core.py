#!/usr/bin/env python
# encoding: utf-8

"""
Simple chat server with a backend built with Redis PubSub.
Each chatroom is backed up by a Redis channel to which
users are subscribed.

Users are stored in a dictionnary.
"""

import json
import os
import redis
import socket
import string
import thread
import time
from flask import Flask, redirect, request, session, url_for
from flask_script import Manager


REDIS_URL = os.environ.get('REDIS_URL', '127.0.0.1:6379')
USERS = {}

redis_server = redis.from_url(REDIS_URL)
app = Flask(__name__)
app.secret_key = 'keep it secret'
app.debug = 'DEBUG'
manager = Manager(app)


__all__ = [
    'app',
    'manager',
    'ChatRoom',
    'SocketServer',
    'runsocketserver'
    ]


class ChatRoom(object):
    """Dummy interface for client registration and update"""

    def __init__(self, channel_name):
        self.channel_name = channel_name
        self.clients = list()
        self.pubsub = redis_server.pubsub()
        self.pubsub.subscribe(self.channel_name)

    def __str__(self):
        return '<ChatRoom {0}>'.format(self.channel_name)

    def __unpack__(self):
        """Yield out data from pubsub"""
        for item in self.pubsub.listen():
            message = item.get('data')
            if item['type'] == 'message':
                yield message

    def register(self, client):
        """Register a client's connection"""
        self.clients.append(client)

    def send(self, client, data):
        """Send data to registered client. Delete on failure"""
        try:
            client.send('<= ' + data + '\n=> ')
        except Exception:  # silent exception, because reasons are obvious
            self.clients.remove(client)

    def publish(self, client, data):
        """Publish in chatroom as given client"""
        redis_server.publish(
            self.channel_name,
            json.dumps(
                {
                    'user': str(client),
                    'message': data
                    }
                )
            )
            
    def run(self):
        """Listen and send messages"""
        for data in self.__unpack__():
            data = json.loads(data)
            publisher = data['user']
            message = data['message']
            for client in self.clients:
                if str(client) != publisher:
                    thread.start_new_thread(self.send, (client, message))

    def start(self):
        thread.start_new_thread(self.run, ())


class SocketServer(object):
    """Simple TCP socket server"""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.rooms = {}
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
                    USERS[name] = {'connection': client}
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
        for user, infos in USERS.items():
            try:
                message = infos['connection'].recv(1024).strip()
            except socket.error:
                continue
            self.process_messages(user, message)
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

    def process_messages(self, user, message):
        """Process messages"""
        client = USERS[user]['connection']
        if message.split()[0] in ['@'+i for i in USERS]:  # DM
            recipient = message.split()[0]
            message = message.split(recipient)[1].lstrip()
            for i, j in USERS.items():
                if '@'+i == recipient:
                    j['connection'].send(
                        '<= ({0}) {1}\n=> '.format(user, message)
                        )
                    break
            client.send('=> ')
        elif message == '/users':  # list users on the server
            client.send('<= Active users are:\n')
            for i in USERS:
                msg = '<= * {0}'.format(i)
                if i == user:
                    msg += ' (**this is you)'
                client.send(msg + '\n')
            client.send('=> ')
        elif message == '/rooms':  # list rooms and their users
            if not self.rooms:
                client.send('<= No active room detected\n')
                client.send('<= Create one, by using "/join room_name"')
            else:
                client.send('<= Active rooms are:\n')
                for name, room in self.rooms.items():
                    client.send(
                        '<= * {0} ({1})\n'.format(name, len(room.clients))
                        )
                client.send('<= End of list\n=> ')
        elif message.startswith('/join'):  # join a chat room
            name = message.split('/join ')[1]
            current_room = USERS[user].get('room')
            if current_room == name:
                client.send('<= You are already here\n')
            elif current_room:
                self.process_messages(user, '/leave')
            elif name not in self.rooms:  # create room
                room = ChatRoom(name)
                self.rooms[name] = room
                room.start()
            else:
                room = self.rooms[name]
            room.register(client)
            USERS[user]['room'] = name
            room.publish(
                client, 'new user joined the room: {0}'.format(user)
                )
            client.send('<= Entering room: {0}\n'.format(name))
            for i, infos in USERS.items():
                if infos['connection'] in room.clients:
                    msg = '<= * {0}'.format(i)
                    if i == user:
                        msg += ' (**this is you)'
                    client.send(msg + '\n')
            client.send('<= End of list\n=> ')
        elif message == '/leave':
            current_room = USERS[user].get('room')
            if current_room:
                message = '{0} has left the room'.format(user)
                client.send('<= Leaving room {0}\n=> '.format(current_room))
                self.rooms[current_room].publish(client, message)
                self.rooms[current_room].clients.remove(client)
                del USERS[user]['room']
        elif message == '/quit':
            self.process_messages(user, '/leave')
            client.send('<= BYE\n')
            del USERS[user]
        elif message.startswith('/'):
            client.send('<= Sorry, unknown command\n=> ')
        elif message and USERS[user].get('room'):
            message = '{0}: {1}'.format(user, message)
            self.rooms[USERS[user].get('room')].publish(client, message)
            client.send('=> ')
        else:
            client.send('<= Join a room to start chatting\n=> ')

@app.route('/')
def index():
    if 'username' in session:
        return '<p>Hello {0}</p>'.format(session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form['username']
        return redirect(url_for('index'))
    return """
    <form action="" method="POST">
      <p><input type=text name="username"/></p>
      <p><input type=submit value="Login"/></p>
    </form>
    """


@manager.command
def runsocketserver(host, port):
    server = SocketServer(host, int(port))
    server.run()

if __name__ == '__main__':
    manager.run()

# EOF
