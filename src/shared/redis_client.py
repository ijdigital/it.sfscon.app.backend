import json
import os
from typing import Any, List, Optional

import redis


class RedisClientHandler:
    def __init__(self, redis_instance: Optional[redis.Redis] = None, port: int = 6379, db: int = 0):
        """
        Initialize the Redis client.

        :param port: Redis server port
        :param db: Redis database number
        """
        if redis_instance:
            self.redis_client = redis_instance
        else:

            #TODO: ...

            # host = "localhost" if os.getenv('V4INSTALLATION', "localhost") not in ('docker', 'docker-monolith') else 'redis'
            host = os.getenv('REDIS_SERVER')
            self.redis_client = redis.Redis(host=host, port=port, db=db)

    @staticmethod
    def get_redis_client(redis_instance: Optional[redis.Redis] = None, port: int = 6379, db: int = 0) -> 'RedisClientHandler':
        return RedisClientHandler(redis_instance, port, db)

    def push_message(self, queue_name: str, message: Any) -> bool:
        """
        Push a message to a specified Redis queue.

        :param queue_name: Name of the queue
        :param message: Message to be pushed (will be JSON serialized)
        :return: True if successful, False otherwise
        """
        try:
            serialized_message = json.dumps(message, default=str)
            self.redis_client.rpush(queue_name, serialized_message)
            return True
        except Exception as e:
            print(f"Error pushing message to queue {queue_name}: {e}")
            raise Exception("FAILED TO SEND REDIS MESSAGE")

    def read_message(self, queue_name: str, timeout: int = 0) -> Optional[Any]:
        """
        Read a message from a specified Redis queue.

        :param queue_name: Name of the queue
        :param timeout: Time to wait for a message (0 means indefinite)
        :return: Deserialized message if available, None otherwise
        """
        try:
            # BRPOP returns a tuple (queue_name, message)
            result = self.redis_client.brpop([queue_name], timeout)
            if result:
                message = result[1]  # Get the message part
                return json.loads(message)
            return None
        except Exception as e:
            print(f"Error reading message from queue {queue_name}: {e}")
            raise Exception("FAILED TO READ REDIS MESSAGE FROM QUEUE")

    def get_queue_length(self, queue_name: str) -> int:
        """
        Get the current length of a queue.

        :param queue_name: Name of the queue
        :return: Length of the queue
        """
        return self.redis_client.llen(queue_name)

    def clear_queue(self, queue_name: str) -> bool:
        """
        Clear all messages from a queue.

        :param queue_name: Name of the queue
        :return: True if successful, False otherwise
        """
        try:
            self.redis_client.delete(queue_name)
            return True
        except Exception as e:
            print(f"Error clearing queue {queue_name}: {e}")
            raise Exception("FAILED TO  CLEAR REDIS QUEUE")

    def get_all_messages(self, queue_name: str) -> List[Any]:
        """
        Get all messages from a queue without removing them.

        :param queue_name: Name of the queue
        :return: List of all messages in the queue
        """
        try:
            messages = self.redis_client.lrange(queue_name, 0, -1)
            return [json.loads(message) for message in messages]
        except Exception as e:
            print(f"Error getting all messages from queue {queue_name}: {e}")
            return []


# Usage example
if __name__ == "__main__":
    import dotenv

    dotenv.load_dotenv()
    redis_handler = RedisClientHandler()
    redis_handler.clear_queue("telegram_send_message")
    message1 = redis_handler.read_message("telegram_send_message")
    message1 = redis_handler.read_message("telegram_send_message")
    message1 = redis_handler.read_message("telegram_send_message")
    message1 = redis_handler.read_message("telegram_send_message")
    message1 = redis_handler.read_message("telegram_send_message")
    message1 = redis_handler.read_message("telegram_send_message")
    message1 = redis_handler.read_message("telegram_send_message")
    message1 = redis_handler.read_message("telegram_send_message")

    # Push messages
    redis_handler.push_message("my_queue", {"key": "value1"})
    redis_handler.push_message("my_queue", {"key": "value2"})

    # Read messages
    message1 = redis_handler.read_message("my_queue")
    message2 = redis_handler.read_message("my_queue")

    print(f"Read messages: {message1}, {message2}")

    # Get queue length
    length = redis_handler.get_queue_length("my_queue")
    print(f"Queue length: {length}")

    # Get all messages without removing them
    all_messages = redis_handler.get_all_messages("my_queue")
    print(f"All messages: {all_messages}")

    # Clear the queue
    redis_handler.clear_queue("my_queue")
