# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import json
import redis
import httpx
import dotenv
import logging
import asyncio

dotenv.load_dotenv()


def setup_logger(logger_name):
    current_file_dir = os.path.dirname(os.path.abspath(__file__))

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # Set the log level

    # Create handlers
    f_handler = logging.FileHandler(f'var/log/opencon/{logger_name}.log')
    f_handler.setLevel(logging.DEBUG)  # Set the log level for the file handler

    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)  # Set the minimum log level for the console handler

    # Create formatters and add it to handlers
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s | %(message)s')
    f_handler.setFormatter(f_format)

    c_format = logging.Formatter('%(message)s')
    c_handler.setFormatter(c_format)

    # Add handlers to the logger
    logger.addHandler(f_handler)
    logger.addHandler(c_handler)

    # Now, you can write to the log using the custom logger
    logger.debug('Logging Initialized')

    return logging.getLogger(logger_name)


async def send_notification(item):
    log = logging.getLogger('push_notifications')

    if not item or 'id' not in item or not item['id']:
        print("not item or 'id' not in item or not item['id']")
        return
        
    try:

        payload = {
            "to": item['id'],
            "title": item['subject'],
            "body": item['message']
        }

        async with httpx.AsyncClient() as client:

            print("SENDING", payload)
            
            res = await client.post('https://exp.host/--/api/v2/push/send', json=payload)
            
            print(res.json())

    except Exception as e:
        
        print("ERROR",e)
    
        log.critical(f"Error sending push notification: {e}")


async def read_redis_queue(queue_name):
    redis_host = os.getenv('REDIS_SERVER')
    redis_client = redis.Redis(host=redis_host, port=6379, db=0)

    log = logging.getLogger('push_notifications')
    log.info("Worker started")

    while True:
        res = redis_client.blpop(queue_name.encode('utf-8'), 5) # *6
        if not res:
            print('.')
            continue

        #breakpoint()

        queue, item = res

        item = item.decode('utf-8')
        item = json.loads(item)

        try:
            await send_notification(item)
        except Exception as e:
            print("EXCEPTION", e)
            continue
            

if __name__ == "__main__":
    setup_logger('push_notifications')
    queue_name = "opencon_push_notification"
    asyncio.run(read_redis_queue(queue_name))
