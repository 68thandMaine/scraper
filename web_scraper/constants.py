"""Default configuration for Ollama and the content agent."""

# Generation: instruction-following, fits 16GB RAM with ChromaDB in Docker.
# qwen2.5:1.5b is ~2x faster than 3b on CPU with minimal quality loss for
# structured CLEAN/DECIDE prompts.
DEFAULT_OLLAMA_MODEL = "qwen2.5:1.5b"

# Embeddings: small, fast; separate from the generation model
DEFAULT_OLLAMA_EMBED_MODEL = "nomic-embed-text"

DEFAULT_OLLAMA_TIMEOUT = 600.0
DEFAULT_MAX_LLM_INPUT_CHARS = 10_000
DEFAULT_OLLAMA_NUM_PREDICT = 1024

# Stays safely under nomic-embed-text's ~2048-token context window
DEFAULT_MAX_EMBED_INPUT_CHARS = 6000

# Retries after the first attempt (3 total attempts)
DEFAULT_OLLAMA_MAX_RETRIES = 2
# Base seconds for linear backoff between retries
DEFAULT_OLLAMA_RETRY_BACKOFF = 2.0
# Seconds to wait for a connection to be established
DEFAULT_OLLAMA_CONNECT_TIMEOUT = 10.0

# Hard cap per ChromaDB network call (seconds)
DEFAULT_CHROMA_TIMEOUT = 30.0
# Retries after the first attempt
DEFAULT_CHROMA_MAX_RETRIES = 2
# Base seconds for linear backoff between retries
DEFAULT_CHROMA_RETRY_BACKOFF = 2.0
