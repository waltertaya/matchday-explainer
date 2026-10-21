from dotenv import load_dotenv
import os

load_dotenv()

# production
DATA_DIR = os.getenv('DATA_DIR', './data')
IFAB_DIR = os.getenv('IFAB_DIR', './ifab')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
ENVIRONMENT=os.getenv("ENVIRONMENT", "production")

#development
NVIDIA_OPENAI_API_KEY = os.getenv('NVIDIA_API_KEY')
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_EMBEDDING_MODEL = os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-vl-1b-v2")
# llama-nemotron-embed-vl-1b-v2 returns 2048-dim text embeddings.
# If you switch models, set EMBEDDING_DIMENSIONS to match, then recreate
# the document_chunks table (manage.py recreate) or run:
#   ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(<dims>);
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "2048"))
#development
NVIDIA_LLM_MODEL = os.getenv("NVIDIA_LLM_MODEL", "openai/gpt-oss-20b")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IFAB_DIR, exist_ok=True)
