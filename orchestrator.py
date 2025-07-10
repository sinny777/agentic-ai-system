# /agentic-ai-system/orchestrator.py

import logging
import json
import time
from redis_client import get_redis_client
from utils import robust_string_to_dict

class Orchestrator:
    def __init__(self):
        self.redis_client = get_redis_client()
        self.logger = logging.getLogger("Orchestrator")
        self.result_streams = [s for s in self.redis_client.keys('results:*')]
        self.error_streams = [s for s in self.redis_client.keys('errors:*')]
        self.stream_keys = self.result_streams + self.error_streams

        if not self.stream_keys:
            self.logger.warning("No result or error streams found. Will listen on default streams.")
            self.stream_keys = ['results:web_search', 'results:summarization', 'errors:web_search', 'errors:summarization']

        for stream in self.stream_keys:
            try:
                self.redis_client.xgroup_create(stream, "orchestrator-group", id='0', mkstream=True)
            except Exception:
                self.logger.info(f"Group for {stream} already exists.")


    def _dispatch_task(self, job_id, task):
        task_agent = task['agent']
        task_stream = f"tasks:{task_agent}"
        payload = {
            "job_id": job_id,
            "task_id": task['task_id'],
            **task['details']
        }
        self.redis_client.xadd(task_stream, payload)
        self.logger.info(f"Dispatched task {task['task_id']} for job {job_id} to stream {task_stream}")
        self.redis_client.hset(f"job:{job_id}", f"task_status:{task['task_id']}", "dispatched")


    def _handle_result(self, job_id, task_id, result):
        self.logger.info(f"Handling result for job {job_id}, task {task_id}.")
        self.redis_client.hset(f"job:{job_id}", f"result:{task_id}", result)
        self.redis_client.hset(f"job:{job_id}", f"task_status:{task_id}", "completed")
        self._check_and_dispatch_next_tasks(job_id)


    def _check_and_dispatch_next_tasks(self, job_id):
        plan_str = self.redis_client.hget(f"job:{job_id}", "plan")
        if not plan_str: return

        plan = json.loads(plan_str)
        all_tasks = plan['tasks']
        job_state = self.redis_client.hgetall(f"job:{job_id}")

        completed_tasks = {
            k.split(':')[1] for k, v in job_state.items() 
            if k.startswith("task_status:") and v == "completed"
        }

        for task in all_tasks:
            task_id = task['task_id']
            if job_state.get(f"task_status:{task_id}") not in ["dispatched", "completed", "failed"]:
                dependencies = set(task['dependencies'])
                if dependencies.issubset(completed_tasks):
                    for key, value in task['details'].items():
                        if isinstance(value, str) and value.startswith("result_from:"):
                            source_task = value.split(':')[1]
                            # The result is stored as a stringified dict, so parse it
                            source_result_str = self.redis_client.hget(f"job:{job_id}", f"result:{source_task}")
                            # source_result = eval(source_result_str)
                            source_result = robust_string_to_dict(source_result_str)
                            # A simple resolver; can be made more robust
                            task['details'][key] = source_result.get('content') or source_result.get('summary')
                    self._dispatch_task(job_id, task)

        # *** NEW: Enhanced job completion check and logging ***
        if len(completed_tasks) == len(all_tasks):
            self.redis_client.hset(f"job:{job_id}", "status", "completed")
            final_state = self.redis_client.hgetall(f"job:{job_id}")
            
            self.logger.info("="*60)
            self.logger.info(f"  JOB COMPLETED: {job_id}")
            self.logger.info("="*60)
            self.logger.info(f"Goal: {plan.get('goal', 'N/A')}")
            
            final_result_task_id = all_tasks[-1]['task_id']
            final_result = final_state.get(f'result:{final_result_task_id}', 'N/A')
            
            self.logger.info(f"\n--- Final Result (from task: {final_result_task_id}) ---\n{final_result}\n")
            self.logger.info("--- Full Job Report ---")
            for key, value in final_state.items():
                if key not in ['plan']:
                    self.logger.info(f"  {key}: {value}")
            self.logger.info("="*60)


    def start_new_job(self, plan: dict):
        job_id = plan['job_id']
        self.logger.info(f"Starting new job: {job_id}")
        self.redis_client.hset(f"job:{job_id}", "status", "running")
        self._check_and_dispatch_next_tasks(job_id)


    def run(self):
        self.logger.info("Orchestrator starting. Listening for results and errors...")
        while True:
            try:
                messages = self.redis_client.xreadgroup(
                    groupname="orchestrator-group",
                    consumername="orchestrator-consumer",
                    streams={key: '>' for key in self.stream_keys},
                    count=1,
                    block=2000
                )

                if not messages:
                    continue

                stream, msg_list = messages[0]
                message_id, data = msg_list[0]
                
                job_id = data.get('job_id')
                # *** FIXED: Read task_id directly from the result/error message ***
                task_id = data.get('task_id')

                if not job_id or not task_id:
                    self.logger.warning(f"Received message without job_id or task_id: {data}")
                    self.redis_client.xack(stream, "orchestrator-group", message_id)
                    continue

                if "results:" in stream:
                    self.logger.info(f"Received result for task {task_id} from {stream}")
                    self._handle_result(job_id, task_id, data.get('result'))

                elif "errors:" in stream:
                    self.logger.error(f"Received error for task {task_id} from {stream}: {data}")
                    self.redis_client.hset(f"job:{job_id}", "status", "failed")
                    self.redis_client.hset(f"job:{job_id}", f"task_status:{task_id}", "failed")
                    self.redis_client.hset(f"job:{job_id}", f"error:{task_id}", data.get('error'))

                self.redis_client.xack(stream, "orchestrator-group", message_id)

            except Exception as e:
                self.logger.error(f"Error in orchestrator loop: {e}", exc_info=True)
                time.sleep(5)