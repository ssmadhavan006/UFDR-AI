# utils/anomaly_detection.py
import os
import sys
import json
import hmac
import hashlib
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from collections import defaultdict
from typing import List, Dict, Any, Optional

__all__ = [
    'detect_temporal_anomalies', 
    'analyze_contact_patterns',
    'generate_timeline_html',
    'generate_contact_graph_html',
    'log_action',
    'get_custody_log',
    'verify_chain_integrity'
]

def log_action(file_id: str, action: str, actor: str, 
               input_ref: Optional[str] = None, 
               output_ref: Optional[str] = None,
               details: Optional[Dict] = None,
               prev_entry_hash: Optional[str] = None,
               server_key: bytes = b"default_key") -> Dict[str, Any]:
    """
    Create a chain of custody log entry with HMAC signature
    
    Args:
        file_id: Unique identifier for the file/evidence
        action: Action performed (upload, parse_lines, qr_detect, etc.)
        actor: Who performed the action (user ID, system, etc.)
        input_ref: Reference to input file/data
        output_ref: Reference to output file/data  
        details: Additional metadata
        prev_entry_hash: Hash of previous entry for chaining
        server_key: Key for HMAC signature
        
    Returns:
        Dictionary containing the log entry with signature
    """
    if details is None:
        details = {}
    
    timestamp = time.time()
    entry = {
        "file_id": file_id,
        "action": action,
        "actor": actor,
        "timestamp": timestamp,
        "input_ref": input_ref,
        "output_ref": output_ref,
        "details": details,
        "prev_entry_hash": prev_entry_hash
    }
    
    # Create HMAC signature
    entry_str = json.dumps(entry, sort_keys=True)
    signature = hmac.new(server_key, entry_str.encode(), hashlib.sha256).hexdigest()
    
    # Add signature and hash of output
    entry["signature"] = signature
    if output_ref:
        entry["sha256_of_output"] = hashlib.sha256(output_ref.encode()).hexdigest()
    
    return entry

def get_custody_log() -> List[Dict[str, Any]]:
    """Get the current chain of custody log"""
    return []  # Placeholder for MVP

def verify_chain_integrity(log_entries: List[Dict[str, Any]]) -> bool:
    """Verify the integrity of chain of custody log"""
    return True  # Placeholder for MVP

def detect_temporal_anomalies(messages: List[Dict[str, Any]], 
                            threshold_messages_per_hour: int = 50) -> Dict[str, Any]:
    """
    Detect temporal anomalies in messages:
    1. Messages sent during odd hours (1-4 AM)
    2. Message spikes (sudden increase in message frequency)
    
    Args:
        messages: List of message dictionaries with 'timestamp' and 'sender' fields
        threshold_messages_per_hour: Threshold for message spike detection
        
    Returns:
        Dictionary with detected anomalies
    """
    if not messages:
        return {"odd_hour_messages": [], "message_spikes": []}
    
    # Convert timestamps to datetime objects
    processed_messages = []
    for msg in messages:
        try:
            if isinstance(msg.get('timestamp'), str):
                try:
                    dt = isoparse(msg['timestamp'].replace('Z', '+00:00'))
                except ValueError:
                    try:
                        dt = datetime.strptime(msg['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except ValueError:
                        try:
                            dt = datetime.strptime(msg['timestamp'], '%Y-%m-%dT%H:%M:%SZ')
                        except ValueError:
                            dt = datetime.now()
            elif isinstance(msg.get('timestamp'), (int, float)):
                dt = datetime.fromtimestamp(msg['timestamp'])
            else:
                dt = datetime.now()
            
            # Create a copy of the message with datetime
            processed_msg = msg.copy()
            processed_msg['datetime'] = dt
            processed_messages.append(processed_msg)
            
        except Exception:
            continue
    
    if not processed_messages:
        return {"odd_hour_messages": [], "message_spikes": []}
    
    # Sort messages by timestamp
    sorted_messages = sorted(processed_messages, key=lambda x: x['datetime'])
    
    # Detect odd hours messages (1-4 AM)
    odd_hours_messages = []
    for msg in sorted_messages:
        if msg['datetime'].hour >= 1 and msg['datetime'].hour <= 4:
            odd_hours_messages.append(msg)
    
    # Group messages by hour for spike detection
    messages_by_hour = defaultdict(list)
    for msg in sorted_messages:
        hour_key = msg['datetime'].strftime('%Y-%m-%d %H')
        messages_by_hour[hour_key].append(msg)
    
    # Detect message spikes
    message_spikes = []
    for hour, hour_messages in messages_by_hour.items():
        if len(hour_messages) >= threshold_messages_per_hour:
            message_spikes.append({
                'hour': hour,
                'count': len(hour_messages),
                'messages': hour_messages[:5]  # Include sample messages
            })
    
    return {
        "odd_hour_messages": odd_hours_messages,
        "message_spikes": message_spikes
    }

def analyze_contact_patterns(messages: List[Dict[str, Any]], 
                           new_contact_window_hours: int = 24) -> Dict[str, Any]:
    """
    Analyze contact patterns to detect:
    1. New contacts in the specified time window
    2. Sudden drops in usual contacts
    
    Args:
        messages: List of message dictionaries with 'timestamp', 'sender', and 'recipient' fields
        new_contact_window_hours: Window to consider contacts as "new"
        
    Returns:
        Dictionary with contact pattern analysis results
    """
    if not messages:
        return {"new_contacts": [], "contact_drops": [], "contact_graph": {}}
    
    # Process messages and ensure datetime field exists
    processed_messages = []
    for msg in messages:
        try:
            if 'datetime' not in msg:
                if isinstance(msg.get('timestamp'), str):
                    try:
                        dt = isoparse(msg['timestamp'].replace('Z', '+00:00'))
                    except ValueError:
                        try:
                            dt = datetime.strptime(msg['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        except ValueError:
                            try:
                                dt = datetime.strptime(msg['timestamp'], '%Y-%m-%dT%H:%M:%SZ')
                            except ValueError:
                                dt = datetime.now()
                elif isinstance(msg.get('timestamp'), (int, float)):
                    dt = datetime.fromtimestamp(msg['timestamp'])
                else:
                    dt = datetime.now()
                
                processed_msg = msg.copy()
                processed_msg['datetime'] = dt
            else:
                processed_msg = msg.copy()
            
            processed_messages.append(processed_msg)
        except Exception:
            continue
    
    if not processed_messages:
        return {"new_contacts": [], "contact_drops": [], "contact_graph": {}}
    
    # Sort messages by timestamp
    sorted_messages = sorted(processed_messages, key=lambda x: x['datetime'])
    
    # Build contact graph
    contact_graph = defaultdict(lambda: defaultdict(list))
    
    # Track first contact time
    first_contact_time = {}
    
    # Track contact frequency by day
    daily_contacts = defaultdict(lambda: defaultdict(int))
    
    for msg in sorted_messages:
        sender = msg.get('sender', '')
        recipient = msg.get('recipient', '')
        
        if not sender or not recipient:
            continue
            
        msg_time = msg['datetime']
        day_key = msg_time.strftime('%Y-%m-%d')
        
        # Add to contact graph
        contact_graph[sender][recipient].append(msg)
        
        # Track first contact
        contact_pair = (sender, recipient)
        if contact_pair not in first_contact_time:
            first_contact_time[contact_pair] = msg_time
            
        # Track daily contact frequency
        daily_contacts[day_key][contact_pair] += 1
    
    # Find new contacts (within specified window)
    if sorted_messages:
        latest_time = max([msg['datetime'] for msg in sorted_messages])
        new_contact_threshold = latest_time - timedelta(hours=new_contact_window_hours)
        
        new_contacts = []
        for contact_pair, first_time in first_contact_time.items():
            if first_time >= new_contact_threshold:
                sender, recipient = contact_pair
                new_contacts.append({
                    'sender': sender,
                    'recipient': recipient,
                    'first_contact_time': first_time,
                    'message_count': len(contact_graph[sender][recipient])
                })
    else:
        new_contacts = []
    
    # Detect sudden drops in contact frequency
    contact_drops = []
    if len(daily_contacts) >= 2:
        # Get the last two days
        days = sorted(daily_contacts.keys())
        if len(days) >= 2:
            yesterday, today = days[-2], days[-1]
            
            # Find contacts that were active yesterday but not today
            for contact_pair, count in daily_contacts[yesterday].items():
                if count > 3 and contact_pair not in daily_contacts[today]:
                    sender, recipient = contact_pair
                    contact_drops.append({
                        'sender': sender,
                        'recipient': recipient,
                        'last_active': yesterday,
                        'previous_count': count
                    })
    
    # Convert contact graph to serializable format
    serializable_graph = {}
    for sender, recipients in contact_graph.items():
        serializable_graph[sender] = {}
        for recipient, msgs in recipients.items():
            serializable_graph[sender][recipient] = len(msgs)
    
    return {
        "new_contacts": new_contacts,
        "contact_drops": contact_drops,
        "contact_graph": serializable_graph
    }

def generate_timeline_html(message_spikes: List[Dict[str, Any]]) -> str:
    """
    Generate an HTML visualization of message timeline using vis.js
    
    Args:
        message_spikes: List of message spikes from temporal anomaly detection
        
    Returns:
        HTML string with vis.js timeline visualization
    """
    if not message_spikes:
        return "<div>No timeline data available</div>"
    
    # Prepare timeline items
    timeline_items = []
    for i, spike in enumerate(message_spikes):
        timeline_items.append({
            "id": i,
            "content": f"Spike: {spike['count']} messages",
            "start": spike['hour'],
            "title": f"Message spike at {spike['hour']}: {spike['count']} messages"
        })
    
    timeline_data = json.dumps(timeline_items)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Message Timeline</title>
        <script src="https://unpkg.com/vis-timeline@7.7.0/dist/vis-timeline-graph2d.min.js"></script>
        <link href="https://unpkg.com/vis-timeline@7.7.0/dist/vis-timeline-graph2d.min.css" rel="stylesheet" type="text/css" />
        <style>
            #timeline {{ width: 100%; height: 400px; border: 1px solid #ccc; }}
        </style>
    </head>
    <body>
        <div id="timeline"></div>
        <script>
            var container = document.getElementById('timeline');
            var items = new vis.DataSet({timeline_data});
            var options = {{
                width: '100%',
                height: '400px',
                margin: {{ item: 20 }},
                type: 'point',
                zoomMin: 1000 * 60 * 60,
                zoomMax: 1000 * 60 * 60 * 24 * 7
            }};
            var timeline = new vis.Timeline(container, items, options);
        </script>
    </body>
    </html>
    """
    
    return html

def generate_contact_graph_html(contact_data: Dict[str, Any]) -> str:
    """
    Generate an HTML visualization of the contact graph using vis.js
    
    Args:
        contact_data: Dictionary with contact graph data
        
    Returns:
        HTML string with vis.js network visualization
    """
    if not contact_data:
        return "<div>No contact graph data available</div>"
    
    # Convert contact graph to vis.js format
    nodes = []
    edges = []
    node_set = set()
    
    for sender, recipients in contact_data.items():
        if sender not in node_set:
            nodes.append({
                "id": sender,
                "label": sender,
                "title": f"Contact: {sender}",
                "color": "#69b3a2"
            })
            node_set.add(sender)
            
        for recipient, count in recipients.items():
            if recipient not in node_set:
                nodes.append({
                    "id": recipient,
                    "label": recipient,
                    "title": f"Contact: {recipient}",
                    "color": "#69b3a2"
                })
                node_set.add(recipient)
            
            edges.append({
                "from": sender,
                "to": recipient,
                "title": f"Messages: {count}",
                "width": max(1, min(10, count // 5)),
                "color": {"color": "#888"}
            })
    
    # Create vis.js data
    graph_data = {
        "nodes": nodes,
        "edges": edges
    }
    
    graph_json = json.dumps(graph_data)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Contact Network Graph</title>
        <script src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"></script>
        <style>
            #network {{ width: 100%; height: 600px; border: 1px solid #ccc; }}
        </style>
    </head>
    <body>
        <div id="network"></div>
        <script>
            var container = document.getElementById('network');
            var data = {graph_json};
            var options = {{
                nodes: {{ 
                    shape: 'dot',
                    size: 16,
                    font: {{ size: 14 }},
                    borderWidth: 2,
                    shadow: true
                }},
                edges: {{ 
                    arrows: 'to',
                    shadow: true,
                    smooth: {{ type: 'continuous' }}
                }},
                physics: {{
                    stabilization: {{ iterations: 150 }},
                    barnesHut: {{ gravitationalConstant: -8000, springConstant: 0.001, springLength: 200 }}
                }},
                interaction: {{ hover: true, tooltipDelay: 100 }}
            }};
            var network = new vis.Network(container, data, options);
        </script>
    </body>
    </html>
    """
    
    return html