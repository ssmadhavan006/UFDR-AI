# backend/ingest.py
import json
import pandas as pd
from typing import List, Dict
from langchain.docstore.document import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from dotenv import load_dotenv
import os
from utils.highlighter import clean_text

load_dotenv()

__all__ = ['load_ufdr_data', 'create_documents', 'ingest_to_chroma']

def load_ufdr_data(file_path: str) -> Dict:
    """Load UFDR data from JSON or CSV"""
    if file_path.endswith('.json'):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    elif file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
        data = {"messages": df.to_dict(orient='records')}
    else:
        raise ValueError("Only JSON/CSV supported for MVP")
    
    # Handle different JSON structures
    if isinstance(data, list):
        # If it's a list, wrap it in a UFDR structure
        data = {"messages": data}
    elif isinstance(data, dict):
        # If it's already a dictionary, ensure it has a messages key
        if "messages" not in data:
            # Look for other possible keys that contain the messages
            for key, value in data.items():
                if isinstance(value, list) and key in ['data', 'records', 'items']:
                    data["messages"] = value
                    break
            else:
                # No list found, create empty messages
                data["messages"] = []
    else:
        # Unexpected data type
        data = {"messages": []}
    
    # Validate and normalize messages
    if not data.get("messages") or not isinstance(data["messages"], list):
        raise ValueError("No valid messages found in the uploaded file. Please check the file format.")
        
    return data

def create_documents(data: Dict) -> List[Document]:
    """Convert UFDR data to LangChain Documents"""
    docs = []
    
    # Extract messages from UFDR structure
    messages = data.get('messages', [])
    
    for i, message in enumerate(messages):
        # Handle different message field names and clean the content
        raw_content = message.get('content') or message.get('message') or message.get('text') or ''
        # Apply aggressive double cleaning to remove any HTML artifacts
        content_text = clean_text(clean_text(raw_content)) if raw_content else ''
        timestamp = message.get('timestamp', '')
        sender = message.get('sender', 'Unknown')
        
        # Create document content
        content = f"[{timestamp}] {sender}: {content_text}"
        
        # Create comprehensive metadata
        metadata = {
            "message_id": str(message.get('message_id', f'msg_{i}')),
            "timestamp": str(timestamp),
            "sender": str(sender),
            "recipient": str(message.get('recipient', '')),
            "channel": str(message.get('channel', '')),
            "media_path": str(message.get('media_path', '')),
            "source_id": i,
            "detected_language": 'en',
            "needs_translation": False,
            "translation_confidence": 1.0,
            "clean_content": content_text  # Store cleaned content for easy access
        }
        
        docs.append(Document(page_content=content, metadata=metadata))
    
    return docs

def ingest_to_chroma(docs: List[Document], persist_dir: str = "./chroma_db"):
    """Ingest docs into ChromaDB with HuggingFace embeddings"""
    try:
        # Explicitly set device to CPU to avoid meta tensor error
        embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"}
        )
        vectorstore = Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            persist_directory=persist_dir
        )
        vectorstore.persist()
        return vectorstore
    except ImportError as e:
        print("\nERROR: Missing required dependencies. Please run:\n")
        print("pip install sentence-transformers\n")
        raise ImportError("Could not import sentence_transformers. Please install with 'pip install sentence-transformers'.") from e
    except Exception as e:
        print(f"\nERROR: Failed to create embeddings: {str(e)}\n")
        raise