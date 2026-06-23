# FORENSIS-AI Database & Document Schemas

This document defines the storage structures used by the FORENSIS-AI application. The system operates on a hybrid storage model combining a relational SQLite audit ledger and a ChromaDB vector store.

---

## 1. Cryptographic Ledger (SQLite3)
*   **Database File**: `data/chain_of_custody.db`
*   **Table Name**: `custody_log`

### Table Schema
| Column Name | SQL Datatype | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique auto-incrementing identifier. |
| `timestamp` | TEXT | NOT NULL | Date and time of the event (ISO 8601 string). |
| `action` | TEXT | NOT NULL | Action executed (e.g. `file_upload`, `search_query`). |
| `actor` | TEXT | NOT NULL | The user ID or system component performing the event. |
| `source_file` | TEXT | NULL | Path to the uploaded report being processed. |
| `line_numbers` | TEXT | NULL | JSON string listing lines processed by the action. |
| `query` | TEXT | NULL | The query string executed (if search query). |
| `results_count`| INTEGER | NULL | Number of records matched or ingested. |
| `confidence` | REAL | NULL | Average confidence score of AI translations/extractions. |
| `hash_value` | TEXT | NOT NULL | SHA-256 hash of this entry's values (including `previous_hash`). |
| `previous_hash`| TEXT | NULL | SHA-256 `hash_value` of the preceding row (chains logs). |
| `signature` | TEXT | NOT NULL | HMAC-SHA256 signature generated using a server key. |
| `details` | TEXT | NULL | JSON string containing custom action metadata. |

### Chaining Mechanics
Each log entry constructs a cryptographic block hash by encoding its row properties along with the preceding block's `hash_value` as a sorted JSON string:
```python
entry_data = {
    "timestamp": timestamp,
    "action": action,
    "actor": actor,
    "source_file": source_file,
    "line_numbers": line_numbers,
    "query": query,
    "results_count": results_count,
    "confidence": confidence,
    "details": details,
    "previous_hash": previous_hash  # Hashed link to prior row
}
entry_json = json.dumps(entry_data, sort_keys=True)
hash_value = hashlib.sha256(entry_json.encode()).hexdigest()
```

---

## 2. Semantic Document Store (ChromaDB)
*   **Collection Folder**: `Source/frontend/chroma_db/`
*   **Model**: HNSW / Cosine Distance
*   **Document Embedding Dimensions**: 384-dimensional vector (`all-MiniLM-L6-v2`)

### Document Payload Schema
Every message block converted to a LangChain `Document` uses the following schema:

#### Page Content Format
```
[{timestamp}] {sender}: {content_text}
```

#### Metadata Dictionary Properties
| Metadata Key | Datatype | Example | Description |
| :--- | :--- | :--- | :--- |
| `message_id` | string | `"msg_14"` | Original identifier of the forensic log entry. |
| `timestamp` | string | `"2025-09-24T02:45:12Z"` | ISO-normalized timestamp of message transmission. |
| `sender` | string | `"alex.johnson@email.com"` | Message sender's identifier. |
| `recipient` | string | `"sarah.williams@email.com"` | Message recipient's identifier. |
| `channel` | string | `"WhatsApp"` | Communication channel name. |
| `media_path` | string | `"media/photo.jpg"` | Associated media file path if present. |
| `source_id` | integer | `14` | Original index location in the raw source array. |
| `detected_language`| string | `"ta"` | ISO 639-1 language code of the raw content. |
| `needs_translation`| boolean | `True` | Flag indicating if translation was applied. |
| `translation_confidence`| float | `0.92` | Gemini API translation confidence score. |
| `clean_content` | string | `"Hello, send the money."`| Raw message string with HTML/CSS tags removed. |
