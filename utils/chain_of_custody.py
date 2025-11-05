"""
Chain of Custody module for AIE - AI Forensic Explorer
Provides functionality for tracking and logging all actions performed on evidence
"""

import hashlib
import hmac
import json
import time
import os
import sqlite3
from datetime import datetime
from pathlib import Path

# Database setup
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chain_of_custody.db")

def init_database():
    """Initialize the chain of custody database"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS custody_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        action TEXT NOT NULL,
        actor TEXT NOT NULL,
        source_file TEXT,
        line_numbers TEXT,
        query TEXT,
        results_count INTEGER,
        confidence REAL,
        hash_value TEXT NOT NULL,
        previous_hash TEXT,
        signature TEXT NOT NULL,
        details TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def compute_file_hash(file_path):
    """Compute SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def compute_data_hash(data):
    """Compute SHA-256 hash of data"""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def get_last_hash():
    """Get the hash of the last entry in the chain"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT hash_value FROM custody_log ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] if result else None

def log_action(action, actor, source_file=None, line_numbers=None, query=None, 
               results_count=None, confidence=None, details=None, server_key=b'aie_secret_key'):
    """
    Log an action in the chain of custody
    
    Args:
        action: The action performed (e.g., "file_upload", "search_query", "export_pdf")
        actor: The user or system component that performed the action
        source_file: The source file being processed
        line_numbers: The line numbers processed
        query: The search query executed
        results_count: The number of results returned
        confidence: The confidence score
        details: Additional details as a dictionary
        server_key: Secret key for signing the entry
    
    Returns:
        The hash of the new entry
    """
    # Initialize database if needed
    if not os.path.exists(DB_PATH):
        init_database()
    
    # Prepare entry data
    timestamp = datetime.now().isoformat()
    
    entry_data = {
        "timestamp": timestamp,
        "action": action,
        "actor": actor,
        "source_file": source_file,
        "line_numbers": line_numbers,
        "query": query,
        "results_count": results_count,
        "confidence": confidence,
        "details": details
    }
    
    # Get previous hash
    previous_hash = get_last_hash()
    
    # Include previous hash in the data to hash
    if previous_hash:
        entry_data["previous_hash"] = previous_hash
    
    # Compute hash of this entry
    entry_json = json.dumps(entry_data, sort_keys=True)
    hash_value = hashlib.sha256(entry_json.encode()).hexdigest()
    
    # Create signature
    signature = hmac.new(server_key, entry_json.encode(), hashlib.sha256).hexdigest()
    
    # Store in database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO custody_log (
        timestamp, action, actor, source_file, line_numbers, query, 
        results_count, confidence, hash_value, previous_hash, signature, details
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        timestamp, action, actor, source_file, 
        json.dumps(line_numbers) if isinstance(line_numbers, (list, dict)) else line_numbers, 
        query, results_count, confidence, hash_value, previous_hash, signature,
        json.dumps(details) if details else None
    ))
    
    conn.commit()
    conn.close()
    
    return hash_value

def get_custody_log(limit=100):
    """
    Get the chain of custody log
    
    Args:
        limit: Maximum number of entries to return
        
    Returns:
        List of log entries
    """
    if not os.path.exists(DB_PATH):
        init_database()
        return []
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM custody_log ORDER BY id DESC LIMIT ?
    ''', (limit,))
    
    results = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # Parse JSON fields
    for row in results:
        if row['details']:
            row['details'] = json.loads(row['details'])
        if row['line_numbers'] and isinstance(row['line_numbers'], str):
            try:
                row['line_numbers'] = json.loads(row['line_numbers'])
            except json.JSONDecodeError:
                pass
    
    return results

def verify_chain_integrity():
    """
    Verify the integrity of the chain of custody
    
    Returns:
        (bool, str): (is_valid, error_message)
    """
    if not os.path.exists(DB_PATH):
        return True, "Chain is empty"
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM custody_log ORDER BY id ASC
    ''')
    
    entries = cursor.fetchall()
    conn.close()
    
    if not entries:
        return True, "Chain is empty"
    
    previous_hash = None
    
    for entry in entries:
        # Reconstruct the data that was hashed
        entry_data = {
            "timestamp": entry['timestamp'],
            "action": entry['action'],
            "actor": entry['actor'],
            "source_file": entry['source_file'],
            "line_numbers": entry['line_numbers'],
            "query": entry['query'],
            "results_count": entry['results_count'],
            "confidence": entry['confidence'],
            "details": json.loads(entry['details']) if entry['details'] else None
        }
        
        if previous_hash:
            entry_data["previous_hash"] = previous_hash
            
            # Check if stored previous hash matches
            if entry['previous_hash'] != previous_hash:
                return False, f"Previous hash mismatch at entry {entry['id']}"
        
        # Compute hash and check
        entry_json = json.dumps(entry_data, sort_keys=True)
        computed_hash = hashlib.sha256(entry_json.encode()).hexdigest()
        
        if computed_hash != entry['hash_value']:
            return False, f"Hash mismatch at entry {entry['id']}"
        
        # Verify signature
        server_key = b'aie_secret_key'  # This should be securely stored and retrieved
        computed_signature = hmac.new(server_key, entry_json.encode(), hashlib.sha256).hexdigest()
        
        if computed_signature != entry['signature']:
            return False, f"Signature verification failed at entry {entry['id']}"
        
        previous_hash = entry['hash_value']
    
    return True, "Chain integrity verified"