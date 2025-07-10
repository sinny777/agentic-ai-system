
import logging
from typing import Optional
import uuid
import json
import ast

def setup_logging():
    """
    Configures basic logging for the application.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def generate_job_id():
    """
    Generates a unique identifier for a job.
    """
    return str(uuid.uuid4())

def robust_string_to_dict(input_str: str) -> Optional[dict]:
    """
    Tries to convert a string into a Python dictionary using multiple strategies.

    Args:
        input_str: The input string to convert.

    Returns:
        A dictionary if conversion is successful, otherwise None.
    """
    if not isinstance(input_str, str):
        print("Error: Input must be a string.")
        return None

    s = input_str.strip() # Remove leading/trailing whitespace

    # Strategy 1: Try parsing as standard JSON
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            # It's valid JSON and it's an object (dict)
            print("Success: Parsed as valid JSON.")
            return data
    except json.JSONDecodeError:
        # Not valid JSON, proceed to the next strategy
        pass

    # Strategy 2: Try parsing as a Python literal (handles single quotes)
    try:
        data = ast.literal_eval(s)
        if isinstance(data, dict):
            # It's a valid Python literal and it's a dict
            print("Success: Parsed as a Python dictionary literal.")
            return data
    except (ValueError, SyntaxError):
        # Not a valid Python literal, proceed to the next strategy
        pass

    # Strategy 3: Try common cleaning steps (e.g., un-escaping single quotes)
    # This is useful for strings like '{\'key\': \'value\'}'
    try:
        cleaned_str = s.replace("\\'", "'")
        data = ast.literal_eval(cleaned_str)
        if isinstance(data, dict):
            print("Success: Parsed after cleaning escaped quotes.")
            return data
    except (ValueError, SyntaxError):
        pass

    # Final Fallback: If all parsing fails
    print("Error: Could not parse the string into a dictionary using any method.")
    # Option 1: Return None (as we are doing here)
    return None
    # Option 2: You could also return a dictionary with an error message
    # return {"error": "Could not parse string", "original_string": input_str}
