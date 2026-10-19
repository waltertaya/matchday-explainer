from rag.parser import Parser
import sys


if __name__ == '__main__':
    parser = Parser(sys.argv[1])

    print(parser.parse())
    