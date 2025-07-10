# /agentic-ai-system/orchestrator.py

import logging, json, time, ast
from redis_client import get_redis_client

class Orchestrator:
    # ... (init and other methods are the same as the previous version) ...
    def __init__(self):
        self.redis_client = get_redis_client()
        self.logger = logging.getLogger("Orchestrator")
        all_streams = self.redis_client.keys('results:*') + self.redis_client.keys('errors:*')
        self.stream_keys = list(set(all_streams)) # Use set to avoid duplicates

        if not self.stream_keys:
            self.logger.warning("No streams found. Will listen on default streams.")
            self.stream_keys = ['results:document_reader', 'results:policy_check', 'results:fraud_detection', 'results:claim_approval']

        for stream in self.stream_keys:
            try:
                self.redis_client.xgroup_create(stream, "orchestrator-group", id='0', mkstream=True)
            except Exception:
                self.logger.info(f"Group for {stream} already exists.")

    def _resolve_data_dependencies(self, job_id, task_details):
        """
        Resolves placeholders like 'data_from:task_id.field' with actual results
        from previous tasks stored in the job's Redis Hash.
        """
        resolved_details = {}
        for key, value in task_details.items():
            if isinstance(value, str) and value.startswith("data_from:"):
                parts = value.split(":", 1)[1].split('.')
                source_task, source_field = parts[0], parts[1]
                
                result_str = self.redis_client.hget(f"job:{job_id}", f"result:{source_task}")
                if not result_str:
                    raise ValueError(f"Could not find result for source task {source_task}")

                # Safely evaluate the string representation of the dictionary
                try:
                    source_result = ast.literal_eval(result_str)
                except (ValueError, SyntaxError) as e:
                    self.logger.error(f"Could not parse result string: {result_str}. Error: {e}")
                    raise
                resolved_details[key] = source_result.get(source_field)
            else:
                resolved_details[key] = value
        # self.logger.debug(f"\n\n>> Resolved details for job > {job_id}: {resolved_details}")
        return resolved_details

    def _check_and_dispatch_next_tasks(self, job_id):
        plan_str = self.redis_client.hget(f"job:{job_id}", "plan")
        if not plan_str: return

        # plan = json.loads(plan_str)

        try:
            plan = ast.literal_eval(plan_str)
            self.logger.debug(f"\n\n=========== Plan for job {job_id}==========: \n{plan}\n=============\n\n")
        except (ValueError, SyntaxError) as e:
            self.logger.error(f"In _check_and_dispatch_next_tasks, could not parse plan: {plan}. Error: {e}")
            raise

        all_tasks = plan['tasks']
        job_state = self.redis_client.hgetall(f"job:{job_id}")

        completed_tasks = {k.split(':')[1] for k, v in job_state.items() if k.startswith("task_status:") and v == "completed"}

        for task in all_tasks:
            task_id = task['task_id']
            if job_state.get(f"task_status:{task_id}") not in ["dispatched", "completed", "failed"]:
                dependencies = set(task['dependencies'])
                # self.logger.info(f"Checking task {task_id} dependencies: {dependencies}")
                if dependencies.issubset(completed_tasks):
                    try:
                        # *** MODIFIED: Use the new resolver function ***
                        task['details'] = self._resolve_data_dependencies(job_id, task['details'])
                        # self.logger.info(f"Dispatching task {task_id} for job {job_id} with resolved details: {task['details']}")
                        self._dispatch_task(job_id, task)
                    except Exception as e:
                        self.logger.error(f"Failed to resolve dependencies for task {task_id}: {e}")
                        self.redis_client.hset(f"job:{job_id}", f"task_status:{task_id}", "failed_dependency")

        # ... (Job completion logging remains the same) ...
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
        task_agent = task['agent']
        task_stream = f"tasks:{task_agent}"
        payload = {
            "job_id": job_id,
            "task_id": task['task_id'],
            **task['details']
        }

        # try:
        #     payload = ast.literal_eval(json.dumps(payload))
        # except (ValueError, SyntaxError) as e:
        #     self.logger.error(f"ERROR In _dispatch_task, could not parse payload: {payload}. Error: {e}")
        #     raise

        self.logger.info(f"\n\nIn _dispatch_task for {task_stream}, with payload: {payload}\n\n")
        try:
            self.redis_client.xadd(task_stream, payload)
        except Exception as e:
            self.logger.error(f"Error in redis_client.xadd: {e}", exc_info=True)
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

                if not messages:
                    continue

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