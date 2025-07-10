# /agentic-ai-system/agents/base_agent.py

import time
import logging
from abc import ABC, abstractmethod
from redis_client import get_redis_client
import governance # Import the new governance module

class BaseAgent(ABC):
    def __init__(self, agent_name: str, task_stream: str, tool_name: str):
        self.agent_name = agent_name
        self.task_stream = task_stream
        self.tool_name = tool_name # The specific tool this agent uses
        self.result_stream_prefix = "results:"
        self.error_stream_prefix = "errors:"
        self.redis_client = get_redis_client()
        self.logger = logging.getLogger(self.agent_name)
        self._register_agent()

    def _register_agent(self):
        self.redis_client.sadd("registered_agents", self.agent_name)
        self.logger.info(f"Agent {self.agent_name} registered.")

    @abstractmethod
    def _perform_task(self, task_data: dict) -> dict:
        pass

    def run(self):
        self.logger.info(f"Agent {self.agent_name} starting. Listening to stream '{self.task_stream}'.")
        try:
            self.redis_client.xgroup_create(self.task_stream, self.agent_name, id='0', mkstream=True)
        except Exception:
            self.logger.info(f"Consumer group '{self.agent_name}' already exists.")

        while True:
            try:
                messages = self.redis_client.xreadgroup(
                    groupname=self.agent_name,
                    consumername=f"{self.agent_name}-consumer",
                    streams={self.task_stream: '>'}, count=1, block=1000
                )

                if not messages: continue

                self.logger.info(f"Received messages: {messages}")
                stream, msg_list = messages[0]
                message_id, task_data = msg_list[0]
                task_id = task_data.get('task_id', 'unknown')
                job_id = task_data.get('job_id', 'unknown')

                self.logger.info(f"Received task {task_id} ({message_id}): {task_data}")

                # --- GOVERNANCE CHECKS ---
                if not governance.check_tool_access(self.agent_name, self.tool_name):
                    raise PermissionError(f"Access denied for tool {self.tool_name}")
                
                if not governance.check_rate_limit(self.agent_name, self.tool_name, limit=100, period=3600):
                    raise Exception("Rate limit exceeded")
                # --- END GOVERNANCE CHECKS ---

                try:
                    result = self._perform_task(task_data)
                    result_stream = f"{self.result_stream_prefix}{self.agent_name}"
                    self.redis_client.xadd(result_stream, {
                        'job_id': job_id, 'task_id': task_id, 'result': str(result)
                    })
                    self.logger.info(f"Task {task_id} completed successfully.")

                except Exception as e:
                    self.logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
                    error_stream = f"{self.error_stream_prefix}{self.agent_name}"
                    self.redis_client.xadd(error_stream, {
                        'job_id': job_id, 'task_id': task_id, 'error': str(e), 'original_task': str(task_data)
                    })

                self.redis_client.xack(self.task_stream, self.agent_name, message_id)

            except Exception as e:
                self.logger.error(f"An unexpected error occurred in the agent loop: {e}", exc_info=True)
                time.sleep(5)