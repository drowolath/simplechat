#!/usr/bin/env python
#encoding: utf-8


import os
from setuptools import setup, find_packages


setup(
    name='simplechat',
    version='0.1',
    packages=find_packages(),
    author='Thomas Ayih-Akakapo',
    author_email='thomas@ayih-akakpo.org',
    description='Simple chat server with Redis PubSub backend',
    license='Apache 2.0',
    include_package_data=True,
    entry_points={
        'console_scripts': ['simplechat=simplechat:manager.run'],
        },
    url='https://github.com/drowolath/simplechat',
    )
