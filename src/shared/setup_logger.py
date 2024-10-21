# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import redis
import logging


class RedisHandler(logging.Handler):
    def __init__(self, redis_client, redis_list_key):
        super().__init__()
        self.redis_client = redis_client
        self.redis_list_key = redis_list_key

    def emit(self, record):
        log_entry = self.format(record)
        self.redis_client.rpush(self.redis_list_key, log_entry)


def setup_redis_logger():
    # Configure the logger
    logger = logging.getLogger('redis_logger')
    logger.setLevel(logging.INFO)

    redis_server = os.getenv('REDIS_SERVER', 'localhost')

    redis_client = redis.Redis(host=redis_server, port=6379, db=0)

    # Create the Redis handler and set a formatter
    redis_handler = RedisHandler(redis_client, 'log_list')
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s ||| %(message)s')
    redis_handler.setFormatter(formatter)

    # Add the Redis handler to the logger
    logger.addHandler(redis_handler)


def setup_file_logger(service: str):
    print(f'\nsetup_file_logger {service}'*10)
    

    logger = logging.getLogger(f'{service}_logger')
    logger.setLevel(logging.INFO)

    handler = logging.FileHandler(f'/var/log/opencon/svc_{service}.log')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - XXX - %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)
