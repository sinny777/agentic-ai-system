
import time
import logging
from abc import ABC, abstractmethod
from redis_client import get_redis_client

class BaseAgent(ABC):
    """
    Abstract Base Class for all agents. It provides the core functionality for
    listening to a Redis Stream, processing messages, and handling errors.
    """
    def __init__(self, agent_name: str, task_stream: str):
        self.agent_name = agent_name
        self.task_stream = task_stream
        self.result_stream_prefix = "results:"
        self.error_stream_prefix = "errors:"
        self.redis_client = get_redis_client()
        self.logger = logging.getLogger(self.agent_name)
        self._register_agent()

    def _register_agent(self):
        """
        Registers the agent's capabilities in a Redis Set for discovery.
        """
        self.redis_client.sadd("registered_agents", self.agent_name)
        self.logger.info(f"Agent {self.agent_name} registered successfully.")

    @abstractmethod
    def _perform_task(self, task_data: dict) -> dict:
        """
        The core logic of the agent. This method must be implemented by
        concrete agent classes. It performs the actual work.
        """
        pass

    def run(self):
        """
        The main loop for the agent. It listens to its designated task stream
        and processes messages one by one.
        """
        self.logger.info(f"Agent {self.agent_name} starting. Listening to stream '{self.task_stream}'.")
        try:
            self.redis_client.xgroup_create(self.task_stream, self.agent_name, id='0', mkstream=True)
        except Exception as e:
            self.logger.info(f"Consumer group '{self.agent_name}' already exists or another error occurred: {e}")

        while True:
            try:
                messages = self.redis_client.xreadgroup(
                    groupname=self.agent_name,
                    consumername=f"{self.agent_name}-consumer",
                    streams={self.task_stream: '>'},
                    count=1,
                    block=1000
                )

                if not messages:
                    continue

                stream, msg_list = messages[0]
                message_id, task_data = msg_list[0]

                self.logger.info(f"Received task {task_data.get('task_id')} ({message_id}): {task_data}")

                try:
                    result = self._perform_task(task_data)

                    result_stream = f"{self.result_stream_prefix}{self.agent_name}"
                    # *** FIXED: Pass the specific task_id from the plan in the result message ***
                    self.redis_client.xadd(result_stream, {
                        'job_id': task_data['job_id'],
                        'task_id': task_data['task_id'],
                        'result': str(result),
                    })
                    self.logger.info(f"Task {task_data['task_id']} ({message_id}) completed successfully.")

                except Exception as e:
                    self.logger.error(f"Error processing task {message_id}: {e}", exc_info=True)
                    error_stream = f"{self.error_stream_prefix}{self.agent_name}"
                    # *** FIXED: Pass the task_id in the error message as well ***
                    self.redis_client.xadd(error_stream, {
                        'job_id': task_data['job_id'],
                        'task_id': task_data.get('task_id', 'unknown'),
                        'error': str(e),
                        'original_task': str(task_data)
                    })

                self.redis_client.xack(self.task_stream, self.agent_name, message_id)

            except Exception as e:
                self.logger.error(f"An unexpected error occurred in the agent loop: {e}", exc_info=True)
                time.sleep(5)