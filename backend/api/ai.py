"""Small, bounded AI requests. Credentials are only needed when AI is used."""
import json
from functools import lru_cache

from openai import OpenAI

from rag import config


@lru_cache(maxsize=256)
def complete_json(instructions, evidence):
    client = OpenAI(timeout=20, max_retries=0)
    completion = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": evidence},
        ],
        response_format={"type": "json_object"},
        max_tokens=700,
        temperature=0.2,
    )
    answer = json.loads(completion.choices[0].message.content or "")
    if not isinstance(answer, dict):
        raise ValueError("Expected a JSON object")
    return answer


def request_data(request):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required")
    return data


def bounded_int(data, key, default, maximum):
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{key} must be an integer between 0 and {maximum}")
    return value
