## Agentic AI System based on Pub/Sub architecture (WIP)

**Please NOTE that this is currently WIP. **

### Prerequisites:

```

#FOR MAC OS (Arm architecture)
export HNSWLIB_NO_NATIVE=1
brew install cmake libomp
declare -x TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

arch -x86_64 /bin/zsh or arch -x86_64 /bin/bash

# For arm64 Pythons:
~/.pyenv/versions/3.10.2/bin/python -m venv venv

# For x86 Pythons:
~/.pyenv/versions/3.10.2_x86/bin/python -m venv venv

pyenv install 3.12
pyenv global 3.12

pip install --upgrade pip

virtualenv venv -p python3.12
source venv/bin/activate

pip install pip-tools

# then create requirements.in file with all dependencies used by your project
# Finally, run the following command to generate a requirements.txt file:
pip-compile requirements.in
or
python -m piptools compile

#pip freeze > requirements.txt
#pip install -U docling
pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

```

-  Create requirements.txt without conflict

```

source ~/.zshrc
source ~/.zshenv   


```

## RUN Redis Docker locally

```
docker run -d --name redis-stack \
-p 6379:6379 -p 8001:8001 \
-e REDIS_ARGS="--requirepass mypassword" \
-v /local-data/:/data \
redis/redis-stack:latest


```

### Core Architectural Principles

This architecture is built on the principles of asynchronous communication, separation of concerns, and centralized state management. Redis serves as the central nervous system for communication and state, while specialized agents handle specific tasks. A `PlannerAgent` orchestrates the overall workflow.

### Multi-Agent System Architecture with AI Governance

<p align="center">
  
  <img width="800" src="./docs/multi-agent-system-diagram.png">

</p>

### Details of the architecture

- Here is a detailed breakdown of the numbered steps in the diagram, which represent the primary workflow of the multi-agent system from receiving a request to delivering the final result.

#### Main Workflow (1-18)

**1. Initiation:** A request is triggered by a client. This could be a User via a web interface, an automated API call, or a scheduled Cron Job.

**2. Job Creation:** The Orchestrator receives the request and creates a new job, logging its initial state (e.g., status: pending) in the Shared Memory (State Store) for tracking.

**3. Task Dispatch:** The Orchestrator sends the high-level task to the task:dispatch channel on the Message Bus. This is the entry point for the agent system.

**4. Planning:** The Planning Agent is subscribed to the task:dispatch channel. It picks up the new task.

**5. Plan Generation:** The Planning Agent communicates with an LLM API to break down the high-level objective into a detailed, step-by-step plan.

**6. Sub-task Distribution:** The Planning Agent publishes the individual steps of the plan as sub-tasks onto the task:general channel. This makes them available to the pool of specialist agents.

**7. Task Execution:** Specialist agents, like Tool Agent A (Search) and Tool Agent B (Code), listen to the task:general channel. They pick up tasks that match their capabilities.

**8. Tool Use:** The specialist agents use their designated external dependencies. For example, the Search Agent queries External Tools & APIs, and the Code Agent uses the Code Execution Sandbox.

**9. Store Artifacts:** The raw output from the tools (e.g., search results, code output) is saved as an "artifact" in the Shared Memory (Artifacts store). This decouples data from the agents.

**10. Publish Intermediate Results:** After completing its task, each Tool Agent publishes a message to the results:intermediate channel, indicating that a piece of the puzzle is ready.

**11. Result Synthesis:** The Synthesis Agent listens to the results:intermediate channel. When results are available, it knows it's time to start assembling them.

**12. Retrieve Artifacts:** The Synthesis Agent retrieves the artifacts it needs from the Shared Memory, which were stored in step 9.

**13. Synthesize Final Answer:** The Synthesis Agent uses an LLM API to combine the various intermediate results into a single, coherent final answer.

**14. Critique and Refinement:** The synthesized answer is sent to the Critique Agent for evaluation. The Critique Agent checks the result for quality, accuracy, and completeness.

**15. Refinement Loop:** If the Critique Agent finds flaws, it can generate new tasks (e.g., "Refine this section," "Verify this fact") and send them back to the task:general channel (step 7), creating an iterative improvement loop.

**16. Job Completion:** Once the result passes critique, the Synthesis Agent publishes the final, validated answer to the job:complete channel.

**17.Notify Orchestrator:** The Orchestrator, listening to the job:complete channel, is notified that the job has finished successfully. It retrieves the final result.

**18. Deliver Result:** The Orchestrator delivers the final result back to the original client that initiated the request in step 1.

**AI Governance Layer (A-G)**
These lettered arrows show how the governance layer oversees the entire process:

**A. Policy Check:** The Orchestrator consults the Policy Engine to ensure the initial request is compliant before starting the process.

**B, C, D. Auditing:** The Planning, Tool, and Synthesis agents all record their actions (plans, tool usage, results) to the Immutable Audit Log for full traceability.

**E. Monitoring:** The Monitoring & Alerting system constantly observes the Audit Log for anomalies, performance issues, or security alerts.

**F. Human Escalation:** For sensitive or high-stakes tasks, the Synthesis Agent can flag a result for review by sending it to the Human Review Gateway.

**G. Human Feedback:** Feedback from a human reviewer can be passed to the Critique Agent to guide the refinement process (step 15), ensuring human oversight is integrated into the loop.

### Further Architectural Enhancements

```
+-------------------+      +-------------------------+      +---------------------+
|   PlannerAgent    |----->|      Redis Streams      |<-----|    Specialized      |
| (LLM-based)       |      | (tasks:*, results:*)    |      |       Agents        |
+-------------------+      +-------------------------+      +---------------------+
        ^                                                            |
        |                                                            v
        |      +-------------------------+      +---------------------+
        +------|      Redis Hash          |<-----|   Aggregator Agent  |
               | (job_id:state)          |      | (or Orchestrator)   |
               +-------------------------+      +---------------------+
```

### 1. State Management with Redis Hashes

To effectively manage the state of complex workflows, we will use a Redis Hash for each job. The key of the hash will be the `job_id`, and the fields within the hash will store the state of each sub-task.

*   **Workflow Initiation:** When a new job is created, the `PlannerAgent` generates a unique `job_id` and creates a new Redis Hash with this ID. The initial state of all sub-tasks is set to "pending".
*   **Aggregator Agent:** An `Aggregator Agent` (or the `PlannerAgent` itself) subscribes to the `results:*` channels. As specialized agents complete their tasks and publish results, the `Aggregator Agent` updates the corresponding field in the Redis Hash for that `job_id`.
*   **Complex Workflows:** This approach allows for sophisticated workflow management. The `PlannerAgent` can query the Redis Hash to check the status of all sub-tasks before initiating the next step in a sequence, enabling dependencies and parallel execution. For example, it can wait for both a "web_search" and a "database_query" to be "complete" before starting a "summarize" task.

### 2. Redis Streams for Reliable Task Management

Instead of using Redis's "fire-and-forget" Pub/Sub, we will use Redis Streams for task management. This provides persistence and guarantees that tasks are not lost if an agent is temporarily unavailable.

*   **Task Creation:** The `PlannerAgent` adds tasks to a specific stream. For example, a web search task would be added to the `tasks:web_search` stream. Each task will include the `job_id` and any necessary data.
*   **Consumer Groups:** Each group of specialized agents (e.g., all `WebSearchAgents`) will form a consumer group for their respective task stream. This allows for load balancing, as multiple agents can consume tasks from the same stream, with each task being processed by only one agent in the group.
*   **Message Acknowledgement:** After an agent successfully processes a task, it acknowledges the message in the stream using the `XACK` command. This removes the message from the pending entries list and ensures it won't be reprocessed.

### 3. Specialized Agents

The architecture will feature multiple, specialized agents, each subscribing to its own task stream. This promotes modularity and separation of concerns.

*   **Agent Channels:** Each type of agent will listen to a specific stream, for example:
    *   `WebSearchAgent` listens to `tasks:web_search`
    *   `DatabaseAgent` listens to `tasks:database_query`
    *   `SummarizationAgent` listens to `tasks:summarize`
*   **Tool Usage:** Each agent is an expert in using a specific tool or set of tools. When an agent receives a task, it executes the relevant tool with the provided data and publishes the result to a `results:[tool_name]` stream (e.g., `results:web_search`).

### 4. Sophisticated PlannerAgent

The `PlannerAgent` is the brain of the operation, responsible for creating and orchestrating the execution of plans.

*   **LLM-Powered Planning:** The `PlannerAgent` uses a large language model (LLM) to break down a high-level goal into a step-by-step plan. This plan should be a structured format like JSON, defining the sequence of tasks, their dependencies, and the specialized agents required for each task.
*   **Dynamic Execution:** The `PlannerAgent` doesn't just create a static plan. It can dynamically adjust the plan based on the results of completed tasks and errors.

### 5. Robust Error Handling

A dedicated error-handling mechanism is crucial for a resilient agentic system.

*   **Error Channel:** When an agent fails to execute a task, it will publish a message to a dedicated error stream, such as `results:error`. This message should include the `job_id`, the details of the error, and the original task payload.
*   **Orchestrator Decision-Making:** The `PlannerAgent` (or a dedicated `ErrorHandlerAgent`) subscribes to the `results:error` stream. When an error is received, the orchestrator can decide on the next course of action, such as:
    *   **Retry:** Re-queue the task for another attempt.
    *   **Alternative Strategy:** Modify the plan to use a different agent or tool.
    *   **Fail:** Mark the job as failed and notify the user or a human operator.

### 6. Agent Discovery and Scaling

For a large-scale system, we need a way to manage and scale agents dynamically.

*   **Agent Registration:** We can use a Redis Set to implement agent discovery. When an agent starts up, it adds its "capability" (e.g., "web_search") to a Redis Set named `registered_agents`. This allows the system to know which types of agents are currently available.
*   **Horizontal Scaling:** Since agents are organized into consumer groups, scaling is as simple as running more instances of an agent. For example, if web searches are a bottleneck, you can launch more `WebSearchAgent` containers. These new agents will automatically join the consumer group and start processing tasks from the `tasks:web_search` stream, distributing the load.

### 7. Governance for Agents and Tools

Governance is essential for ensuring the responsible and secure operation of the agentic system.

*   **Tool Access Control:** A central configuration, perhaps stored in a Redis Hash, can define which agents have access to which tools. Before an agent attempts to use a tool, it can query this configuration to verify its permissions.
*   **Rate Limiting and Quotas:** To prevent abuse and manage costs (especially for paid APIs), you can implement rate limiting for tools. Redis is well-suited for this, using its atomic increment and expiration features to track usage per agent or per API key.
*   **Auditing and Logging:** Every action taken by an agent, every tool call, and every decision made by the `PlannerAgent` should be logged. Redis Streams can be used for a persistent, append-only log of all activities, which can be invaluable for auditing and debugging.
*   **Human-in-the-Loop:** For sensitive actions, the `PlannerAgent` can be configured to require human approval. Before dispatching a high-risk task, it can publish a message to a `human_approval` stream and wait for an external confirmation before proceeding.

This architecture provides a solid foundation for building a wide variety of Agentic AI solutions that are scalable, resilient, and governable. By leveraging the powerful and versatile features of Redis, you can create a system that is both high-performing and adaptable to your specific needs.