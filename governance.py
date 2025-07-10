
import logging
from redis_client import get_redis_client

logger = logging.getLogger("Governance")
redis_client = get_redis_client()

def register_tool_access(agent_name: str, allowed_tools: list[str]):
    """
    Registers the tools an agent is allowed to use in a Redis Hash.
    KEY: "gov:permissions"
    FIELD: agent_name
    VALUE: a comma-separated string of tool names
    """
    redis_client.hset("gov:permissions", agent_name, ",".join(allowed_tools))
    logger.info(f"Registered tool access for {agent_name}. Allowed: {allowed_tools}")

def check_tool_access(agent_name: str, tool_name: str) -> bool:
    """
    Checks if an agent has permission to use a specific tool.
    """
    allowed_tools_str = redis_client.hget("gov:permissions", agent_name)
    if not allowed_tools_str:
        logger.warning(f"Governance Deny: No permissions found for agent '{agent_name}'.")
        return False
    
    allowed_tools = allowed_tools_str.split(',')
    if tool_name not in allowed_tools:
        logger.warning(f"Governance Deny: Agent '{agent_name}' is not allowed to use tool '{tool_name}'.")
        return False
    
    logger.info(f"Governance Allow: Agent '{agent_name}' has permission for tool '{tool_name}'.")
    return True

def check_rate_limit(agent_name: str, tool_name: str, limit: int, period: int) -> bool:
    """
    Checks if an agent has exceeded its rate limit for a tool.
    - limit: Max number of calls.
    - period: Time window in seconds.
    """
    key = f"gov:rate_limit:{agent_name}:{tool_name}"
    current_calls = redis_client.incr(key)

    # If this is the first call in the window, set the expiration
    if current_calls == 1:
        redis_client.expire(key, period)
    
    if current_calls > limit:
        logger.warning(f"Governance Deny: Rate limit of {limit}/{period}s exceeded for {agent_name} on tool {tool_name}.")
        return False
        
    return True