#!/usr/bin/env python
# encoding: utf-8

"""
Simple chat server with a backend build with Redis PubSub.
Each chatroom is backed up by a Redis channel to which
users are subscribed.

Users are stored in a dictionnary.
"""


# EOF
