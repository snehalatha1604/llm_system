from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
import faiss
import numpy as np
import os
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()

model = NVIDIAEmbeddings(
    model="nvidia/llama-3.2-nv-embedqa-1b-v2", 
    api_key=os.getenv("NVIDIA_API_KEY"), 
    truncate="NONE"
)

@lru_cache(maxsize=50)
def get_embeddings(texts: tuple) -> np.array:  # Note: texts must be hashable
    return np.array(model.embed_documents(list(texts)))

def get_batch_embeddings(texts: list, batch_size: int = 32) -> np.array:
    """Process embeddings in batches for better performance"""
    # Filter out empty texts
    valid_texts = [text.strip() for text in texts if text and text.strip()]
    if not valid_texts:
        return None
        
    all_embeddings = []
    for i in range(0, len(valid_texts), batch_size):
        batch = valid_texts[i:i + batch_size]
        if batch:  # Ensure batch is not empty
            batch_embeddings = model.embed_documents(batch)
            all_embeddings.extend(batch_embeddings)
    return np.array(all_embeddings) if all_embeddings else None

def build_faiss_index(embeddings):
    dim = embeddings[0].shape[0]
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings))
    return index

def save_faiss_index(index, filepath):
    """Save FAISS index to disk"""
    faiss.write_index(index, filepath)

def load_faiss_index(filepath):
    """Load FAISS index from disk"""
    if os.path.exists(filepath):
        return faiss.read_index(filepath)
    return None
