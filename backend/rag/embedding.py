
import hashlib
import json
from pathlib import Path
from typing import List, Optional

import numpy as np
from openai import OpenAI

from . import config


EMBED_CACHE = Path(config.DATA_DIR) / "embeddings_cache.json"
EXPECTED_DIMENSIONS = config.EMBEDDING_DIMENSIONS


def _load_cache():
    if EMBED_CACHE.exists():
        return json.loads(EMBED_CACHE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict):
    EMBED_CACHE.parent.mkdir(parents=True, exist_ok=True)
    EMBED_CACHE.write_text(
        json.dumps(cache),
        encoding="utf-8",
    )


def _cache_key(text: str, model: str, input_type: str) -> str:
    value = f"{model}:{input_type}:{text}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def embed_texts(
    texts: List[str],
    model: Optional[str] = None,
    input_type: str = "query",
) -> List[np.ndarray]:
    """Generate and cache embeddings for text inputs."""

    if not texts:
        return []

    model = model or config.EMBEDDING_MODEL
    cache = _load_cache()

    results = [None] * len(texts)
    missing = {}

    for i, text in enumerate(texts):
        key = _cache_key(text, model, input_type)

        if key in cache:
            results[i] = cache[key]
        else:
            # Deduplicate repeated text within this request.
            missing.setdefault(key, text)

    if missing:
        unique_keys = list(missing.keys())
        unique_texts = list(missing.values())

        client = OpenAI(timeout=20, max_retries=0)
        response = client.embeddings.create(
            input=unique_texts,
            model=model,
            encoding_format="float",
            extra_body={
                "modality": ["text"] * len(unique_texts),
                "input_type": input_type,
                "truncate": "NONE",
            },
        )

        vectors_by_key = {}

        for key, item in zip(unique_keys, response.data):
            vector = item.embedding

            # print(f"Embedding for key {key}: {vector[:5]}... (length: {len(vector)})")

            if len(vector) != EXPECTED_DIMENSIONS:
                raise ValueError(
                    f"Expected {EXPECTED_DIMENSIONS} dimensions, "
                    f"received {len(vector)}"
                )

            vectors_by_key[key] = vector
            cache[key] = vector

        _save_cache(cache)

        for i, text in enumerate(texts):
            key = _cache_key(text, model, input_type)

            if results[i] is None:
                results[i] = vectors_by_key[key]

    return [np.asarray(vector, dtype=np.float32) for vector in results]
