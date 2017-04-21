#!/usr/bin/env python
# encoding: utf-8

"""
Simple chat server with a backend build with Redis PubSub.
Each chatroom is backed up by a Redis channel to which
users are subscribed.

Users are stored in a dictionnary.
"""

import os
import redis
import thread


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
            client.send(data)
        except Exception:  # silent exception, because reasons are obvious
            self.clientss.remove(client)
        
    def run(self):
        """Listen and send messages"""
        pass  # filter publisher out

    def start(self):
        thread.start_new_thread(self.run, ())
            
# EOF
