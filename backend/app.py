from rag.parser import Parser
from rag.chunker import chunk_text_by_tokens
import sys


if __name__ == '__main__':
    parser = Parser(sys.argv[1])

    text, metadata = parser.parse()

    print(f'metadata: {metadata}')
    print(f'chunks: {chunk_text_by_tokens(text)}')
