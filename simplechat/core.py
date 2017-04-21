#!/usr/bin/env python
# encoding: utf-8

"""
Simple chat server with a backend build with Redis PubSub.
Each chatroom is backed up by a Redis channel to which
users are subscribed.

Users are stored in a dictionnary.
"""

import json
import os
import redis
import socket
import thread
import time


REDIS_URL = os.environ.get('REDIS_URL', '127.0.0.1:6379')
USERS = {}

redis_server = redis.from_url(REDIS_URL)


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
            client.send('\n<= ' + data + '\n=> ')
        except Exception:  # silent exception, because reasons are obvious
            self.clientss.remove(client)

    def publish(self, client, data):
        """Publish in chatroom as given client"""
        redis_server.publish(
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
                    thread.start_new_thread(self.send, client, data['message'])

    def start(self):
        thread.start_new_thread(self.run, ())


class SocketServer(object):
    """Simple TCP socket server"""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.rooms = list()
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
                elif name:
                    client.setblocking(False)
                    USERS[name] = {'connection': client}
                    client.send('<= Welcome {0}\n=> '.format(name))
                    break
                else:
                    client.send('<= Invalid username\n')
                    
        while True:
            try:
                client, address = self.socket.accept()
            except socket.error:
                break
            msg = 'Welcome to the simplechat chat server'
            client.send('<= {0}\n'.format(msg))
            thread.start_new_thread(_inner_thread, (client,))

    def recv(self):
        """Continuously accept incoming messages"""
        for user, infos in USERS.items():
            try:
                message = infos['connection'].recv(1024).strip()
            except socket.error:
                continue
            process_messages(user, message)
            client.send('\n=> ')
            time.sleep(.1)

    def protocol(self, user, message):
        """Process messages"""
        client = USERS[user]['connection']
        if message.split()[0] in ['@'+i for i in USERS]:  # DM
            recipient = message.split()[0]
            message = message.split(recipient)[1]
            for i, j in USERS.items():
                if '@'+i == recipient:
                    client.send('<= ({0}) {1}'.format(user, message))
                    break
        elif message == '/rooms':  # list rooms and their users
            if not self.rooms:
                conn.send('<= No active room detected')
                conn.send('<= Create one, by using "/join room_name"')
            else:
                conn.send('<= Active rooms are:\n')
                for room in self.rooms:
                    conn.send(
                        '<= * {0} ({1})\n'.format(
                            room.channel_name,
                            len(room.clients))
                        )
                conn.send('<= End of list')
        elif message.startswith('/join'):  # join a chat room
            name = message.split('/join ')[1]
            current_room = if USERS[user].get('room')
            if current_room == name:
                client.send('<= You are already here')
            elif current_room:
                self.protocol(user, '/leave {0}'.format(current_room))
            else:
                room = filter(lambda x: x.channel_name==name, self.rooms)
                if not room:  # create it
                    room = ChatRoom(name)
                    self.rooms.append(room)
                    room.start()
                else:
                    room = room[0]
                room.register(client)
                room.publish(
                    client, 'new user joined the room: {0}'.format(user)
                    )
                client.send('<= Entering room: {0}'.format(name))
                for i, infos in USERS.items():
                    if i == user:
                        client.send('<= * {0} (**this is you)'.format(user))
                    elif infos['connection'] in room.clients:
                        client.send('<= * {0}'.format(user))
                client.send('<= End of list')
# EOF
