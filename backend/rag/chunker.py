import tiktoken

from typing import List

def chunk_text_by_tokens(text: str, chunk_size: int = 512, overlap: int = 64, encoding_name: str = "cl100k_base") -> List[str]:
    """  """
    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(text)

    chunks = []

    tokens_length = len(tokens)
    start = 0

    while start < tokens_length:
        end = min(start + chunk_size, tokens_length)
        chunk_token = tokens[start:end]
        chunk_text = encoding.decode(chunk_token)

        chunks.append(chunk_text)

        if end == tokens_length:
            break

        start += chunk_size - overlap

    return chunks
