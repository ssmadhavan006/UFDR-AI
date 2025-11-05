# backend/search_engine.py
import re
from typing import List, Dict
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from backend.ingest import create_documents

__all__ = ['hybrid_search']

def keyword_filter(docs: List, query: str) -> List:
    """Simple BM25-style keyword match (MVP)"""
    tokens = query.lower().split()
    filtered = []
    for doc in docs:
        content = doc.page_content.lower()
        if any(token in content for token in tokens):
            filtered.append(doc)
    return filtered

def hybrid_search(vectorstore, query: str, top_k: int = 10):
    """Vector search + keyword prefilter (MVP hybrid)"""
    try:
        # First check if vectorstore is valid
        if not vectorstore:
            print("Vectorstore is None")
            return []
        
        # Step 1: Use the vectorstore's built-in similarity search
        results = vectorstore.similarity_search(query, k=top_k)
        print(f"Search for '{query}' returned {len(results)} results")
        
        # Debug: Print first result to see structure
        if results:
            print(f"First result metadata keys: {list(results[0].metadata.keys())}")
            print(f"First result content preview: {results[0].page_content[:100]}...")
        
        return results
    except Exception as e:
        print(f"Search error for query '{query}': {e}")
        import traceback
        traceback.print_exc()
        return []