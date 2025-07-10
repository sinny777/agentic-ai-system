# /agentic-ai-system/orchestrator.py

import logging
import json
import time
import ast
from redis_client import get_redis_client

class Orchestrator:
    def __init__(self):
        self.redis_client = get_redis_client()
        self.logger = logging.getLogger("Orchestrator")
        all_streams = self.redis_client.keys('results:*') + self.redis_client.keys('errors:*')
        self.stream_keys = list(set(all_streams))

        if not self.stream_keys:
            self.logger.warning("No streams found. Will listen on default insurance streams.")
            self.stream_keys = ['results:document_reader', 'results:policy_check', 'results:fraud_detection', 'results:claim_approval']

        for stream in self.stream_keys:
            try:
                self.redis_client.xgroup_create(stream, "orchestrator-group", id='0', mkstream=True)
            except Exception:
                self.logger.info(f"Group for {stream} already exists.")

    def _serialize_payload(self, payload: dict) -> dict:
        """
        Ensures all values in the payload are Redis-compatible types.
        Converts dicts and lists to JSON strings.
        """
        serialized_payload = {}
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                serialized_payload[key] = json.dumps(value)
            else:
                serialized_payload[key] = value
        return serialized_payload

    def _resolve_data_dependencies(self, job_id, task_details):
        resolved_details = {}
        for key, value in task_details.items():
            if isinstance(value, str) and value.startswith("data_from:"):
                parts = value.split(":", 1)[1].split('.', 1)
                source_task, source_field = parts[0], parts[1]
                
                result_str = self.redis_client.hget(f"job:{job_id}", f"result:{source_task}")
                if not result_str:
                    raise ValueError(f"Could not find result for source task {source_task}")

                try:
                    source_result = ast.literal_eval(result_str)
                except (ValueError, SyntaxError) as e:
                    self.logger.error(f"Could not parse result string: {result_str}. Error: {e}")
                    raise

                # This can be made more robust for nested field access
                resolved_details[key] = source_result.get(source_field)
            else:
                resolved_details[key] = value
        return resolved_details

    def _check_and_dispatch_next_tasks(self, job_id):
        plan_str = self.redis_client.hget(f"job:{job_id}", "plan")
        if not plan_str: return

        plan = json.loads(plan_str)
        all_tasks = plan['tasks']
        job_state = self.redis_client.hgetall(f"job:{job_id}")

        completed_tasks = {k.split(':')[1] for k, v in job_state.items() if k.startswith("task_status:") and v == "completed"}

        for task in all_tasks:
            task_id = task['task_id']
            if job_state.get(f"task_status:{task_id}") not in ["dispatched", "completed", "failed"]:
                dependencies = set(task['dependencies'])
                if dependencies.issubset(completed_tasks):
                    try:
                        task['details'] = self._resolve_data_dependencies(job_id, task['details'])
                        self._dispatch_task(job_id, task)
                    except Exception as e:
                        self.logger.error(f"Failed to resolve dependencies or dispatch for task {task_id}: {e}")
                        self.redis_client.hset(f"job:{job_id}", f"task_status:{task_id}", "failed_dependency")

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

    def _dispatch_task(self, job_id, task):
        """
        Dispatches a task to the appropriate agent stream after serializing its payload.
        """
        task_agent = task['agent']
        task_stream = f"tasks:{task_agent}"
        
        # Original payload might contain nested dicts
        raw_payload = {
            "job_id": job_id,
            "task_id": task['task_id'],
            **task['details']
        }
        
        # *** FIXED: Serialize the payload before sending to Redis ***
        serialized_payload = self._serialize_payload(raw_payload)
        
        self.redis_client.xadd(task_stream, serialized_payload)
        self.logger.info(f"Dispatched task {task['task_id']} for job {job_id} to stream {task_stream}")
        self.redis_client.hset(f"job:{job_id}", f"task_status:{task['task_id']}", "dispatched")

    def _handle_result(self, job_id, task_id, result):
        self.logger.info(f"Handling result for job {job_id}, task {task_id}.")
        self.redis_client.hset(f"job:{job_id}", f"result:{task_id}", result)
        self.redis_client.hset(f"job:{job_id}", f"task_status:{task_id}", "completed")
        self._check_and_dispatch_next_tasks(job_id)

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
                if not messages: continue

                stream, msg_list = messages[0]
                message_id, data = msg_list[0]
                
                job_id = data.get('job_id')
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