
import hashlib
import json
import logging
import os
import tempfile
from functools import lru_cache
from threading import RLock
from pathlib import Path
from typing import List, Optional

import numpy as np
from openai import OpenAI

from . import config


SEED_CACHE = Path(config.DATA_DIR) / "embeddings_cache.json"
EMBED_CACHE = Path(config.DATA_DIR) / "embeddings_cache.local.json"
EXPECTED_DIMENSIONS = config.EMBEDDING_DIMENSIONS
_cache_lock = RLock()


@lru_cache(maxsize=4)
def _read_cache(filename, mtime, size):
    try:
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        logging.getLogger(__name__).warning("Ignoring unreadable embedding cache %s", filename)
        return {}


def _cache_file(path):
    try:
        stat = path.stat()
        return _read_cache(str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}


def _load_cache():
    with _cache_lock:
        return {**_cache_file(SEED_CACHE), **_cache_file(EMBED_CACHE)}


def _save_cache(cache: dict):
    # Seed vectors are read-only. Write only additions to a gitignored file;
    # atomic replacement prevents a concurrent request reading half a JSON file.
    with _cache_lock:
        EMBED_CACHE.parent.mkdir(parents=True, exist_ok=True)
        seed = _cache_file(SEED_CACHE)
        additions = {key: value for key, value in cache.items() if seed.get(key) != value}
        local = {**_cache_file(EMBED_CACHE), **additions}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=EMBED_CACHE.parent,
                                             prefix=".embedding-", delete=False) as stream:
                temporary = stream.name
                json.dump(local, stream)
            os.replace(temporary, EMBED_CACHE)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


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

        if isinstance(cache.get(key), list) and len(cache[key]) == EXPECTED_DIMENSIONS:
            results[i] = cache[key]
        else:
            # Deduplicate repeated text within this request.
            missing.setdefault(key, text)

    if missing:
        unique_keys = list(missing.keys())
        unique_texts = list(missing.values())

        client = OpenAI(timeout=20, max_retries=0)
        options = {"input": unique_texts, "model": model, "encoding_format": "float"}
        if model.startswith("text-embedding-3"):
            options["dimensions"] = EXPECTED_DIMENSIONS
        response = client.embeddings.create(**options)
        if len(response.data) != len(unique_keys):
            raise ValueError("Embedding service returned an unexpected number of vectors")

        vectors_by_key = {}

        for key, item in zip(unique_keys, response.data):
            vector = item.embedding

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
