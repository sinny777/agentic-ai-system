
import redis
import os

# It's good practice to use environment variables for configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "mypassword")

# Create a reusable connection pool
redis_pool = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, db=0, decode_responses=True)

def get_redis_client():
    """
    Returns a Redis client instance from the connection pool.
    """
    return redis.Redis(connection_pool=redis_pool)

# A client instance for general use
redis_client = get_redis_client()

# Ensure the server is connected
try:
    redis_client.ping()
    print("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")
    print("Please ensure Redis is running and accessible at {REDIS_HOST}:{REDIS_PORT}")