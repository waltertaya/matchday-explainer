from rag.parser import Parser
from rag.chunker import chunk_text_by_tokens
from rag.embedding import embed_texts
import sys


if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage = f'Usage:\n\tpython3 app.py path_to_file_to_ingest\n\tnote only file at a time'
        print(usage)
        exit(1)
    
    path = sys.argv[1]
    parser = Parser(path)

    texts, metadata = parser.parse()
    chunks = chunk_text_by_tokens(texts)

    print(f'First 5 embeddings: {embed_texts(chunks)}')
