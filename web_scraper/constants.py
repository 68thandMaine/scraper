"""Default configuration for Ollama and the content agent."""

# Generation: instruction-following, fits 16GB RAM with ChromaDB in Docker
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"

# Embeddings: small, fast; separate from the generation model
DEFAULT_OLLAMA_EMBED_MODEL = "nomic-embed-text"

DEFAULT_OLLAMA_TIMEOUT = 600.0
DEFAULT_MAX_LLM_INPUT_CHARS = 10_000
DEFAULT_OLLAMA_NUM_PREDICT = 2048

# Stays safely under nomic-embed-text's ~2048-token context window
DEFAULT_MAX_EMBED_INPUT_CHARS = 6000
