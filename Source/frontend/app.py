# frontend/app.py
import streamlit as st
import streamlit.components.v1 as components
import os
import sys
import json
import re
import requests
from datetime import datetime
from dateutil.parser import isoparse
# Ensure project root is in sys.path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from backend.ingest import load_ufdr_data, create_documents, ingest_to_chroma
from backend.search_engine import hybrid_search
from utils.highlighter import highlight_entities, clean_text, highlight_query_terms
from utils.pdf_generator import generate_pdf_report
from utils.chain_of_custody import log_action, get_custody_log, verify_chain_integrity
from utils.anomaly_detection import (
    detect_temporal_anomalies,
    analyze_contact_patterns,
    generate_contact_graph_html,
    generate_timeline_html
)
from utils.gemini_client import GeminiClient
from utils.translation import TranslationManager

# Initialize
st.set_page_config(page_title="FORENSIS-AI MVP", layout="wide")
st.title("🕵️ FORENSIS-AI — UFDR Triage MVP")

# Initialize translation manager
if 'translation_manager' not in st.session_state:
    st.session_state.translation_manager = TranslationManager()

# Initialize language options
SUPPORTED_LANGUAGES = {
    'auto': 'Auto Detect',
    'en': 'English',
    'ta': 'Tamil',
    'hi': 'Hindi',
    'bn': 'Bengali',
    'te': 'Telugu',
    'mr': 'Marathi'
}

# Initialize session state
if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None
    st.session_state.data_loaded = False
    st.session_state.uploaded_data = None
    st.session_state.analysis_results = None
    
# Initialize session state for behavioral intelligence features
if 'temporal_anomalies' not in st.session_state:
    st.session_state.temporal_anomalies = {}
if 'contact_patterns' not in st.session_state:
    st.session_state.contact_patterns = {}
if 'ai_suggestions' not in st.session_state:
    st.session_state.ai_suggestions = []

# File upload section
st.subheader("📤 Upload UFDR Data")
upload_col1, upload_col2 = st.columns([1, 1])

with upload_col1:
    uploaded_file = st.file_uploader("Upload your UFDR JSON file", type=['json'])
    
    if uploaded_file is not None:
        try:
            with st.spinner("Processing UFDR data..."):
                # Load and validate the uploaded JSON data
                data = json.load(uploaded_file)
                if isinstance(data, str):
                    data = json.loads(data)
                
                # Validate UFDR structure
                if not isinstance(data, dict) or 'messages' not in data or not isinstance(data['messages'], list):
                    st.error("Invalid UFDR format. Please check the file structure.")
                    st.stop()

                # Handle any double-encoded strings in the data
                list_keys = ["messages", "chain_of_custody", "media_analysis", "evidence_highlights", "manifest"]
                for key in list_keys:
                    if key in data and isinstance(data[key], list):
                        for i, item in enumerate(data[key]):
                            if isinstance(item, str):
                                data[key][i] = json.loads(item)
                
                st.session_state.uploaded_data = data
                total_messages = len(data["messages"])
                
                # Process messages with a progress bar
                progress_bar = st.progress(0)
                status_placeholder = st.empty()
                
                # Process each message
                for i, msg in enumerate(data["messages"]):
                    progress = int((i + 1) * 100 / total_messages)
                    progress_bar.progress(progress)
                    
                    # Clean and normalize message content
                    if 'content' in msg and msg['content']:
                        # First remove any HTML/CSS artifacts
                        msg['content'] = clean_text(msg['content'])
                        # Additional cleaning for special characters
                        msg['content'] = re.sub(r'<[^>]+>', '', msg['content'])  # Remove any remaining HTML
                        msg['content'] = re.sub(r'[^\S\r\n]+', ' ', msg['content'])  # Normalize whitespace
                        msg['content'] = msg['content'].strip()
                        
                        # Normalize timestamp
                        if 'timestamp' in msg:
                            try:
                                dt = isoparse(msg['timestamp'])
                                msg['timestamp'] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                            except:
                                pass
                        
                        # Handle translation if needed
                        try:
                            translated_text, original_text, confidence = st.session_state.translation_manager.translate_text(msg['content'])
                            msg['detected_language'] = st.session_state.translation_manager.detect_language(msg['content'])
                            msg['needs_translation'] = msg['detected_language'] != 'en'
                            
                            if msg['needs_translation']:
                                msg['original_text'] = msg['content']
                                msg['content'] = translated_text
                                msg['translation_confidence'] = confidence
                        except:
                            pass
                            
                    data["messages"][i] = msg
                
                # Clean up existing vectorstore to ensure fresh, clean data
                chroma_db_path = os.path.join(PROJECT_ROOT, "frontend", "chroma_db")
                if os.path.exists(chroma_db_path):
                    import shutil
                    try:
                        shutil.rmtree(chroma_db_path)
                    except Exception as e:
                        pass  # Continue even if cleanup fails
                
                # Create and ingest documents with cleaned content
                docs = create_documents(data)
                vectorstore = ingest_to_chroma(docs, persist_dir=chroma_db_path)
                st.session_state.vectorstore = vectorstore
                st.session_state.data_loaded = True
                
                # Clear progress indicators
                progress_bar.empty()
                status_placeholder.empty()
                
                st.success(f"✅ UFDR data processed successfully! ({total_messages} messages)")
                
        except Exception as e:
            st.error("Error processing the file. Please check the format and try again.")

with upload_col2:
    if st.button("Load Sample Data"):
        with st.spinner("Loading sample UFDR data..."):
            sample_path = os.path.join(PROJECT_ROOT, "data", "sample_ufdr.json")
            data = load_ufdr_data(sample_path)
            st.session_state.uploaded_data = data
            
            # Clean up existing vectorstore to ensure fresh, clean data
            chroma_db_path = os.path.join(PROJECT_ROOT, "frontend", "chroma_db")
            if os.path.exists(chroma_db_path):
                import shutil
                try:
                    shutil.rmtree(chroma_db_path)
                except Exception as e:
                    pass  # Continue even if cleanup fails
            
            # Create and ingest documents with cleaned content
            docs = create_documents(data)
            vectorstore = ingest_to_chroma(docs, persist_dir=chroma_db_path)
            st.session_state.vectorstore = vectorstore
            st.session_state.data_loaded = True
            st.success("✅ Sample UFDR loaded!")

# Instructions when no data is loaded
if not st.session_state.data_loaded:
    st.info("⬆️ Please upload a UFDR JSON file or load the sample data to begin analysis.")

# Behavioral Intelligence Section
if st.session_state.data_loaded:
    st.subheader("🧠 Behavioral Intelligence")
    
    # Option to run behavioral analysis
    if st.button("📊 Run Behavioral Analysis", key="run_behavioral_analysis"):
        with st.spinner("Analyzing communication patterns..."):
            try:
                # Get messages
                messages = st.session_state.uploaded_data.get('messages', [])
                if not messages:
                    st.error("No messages found to analyze.")
                    st.stop()
                
                # Format messages for analysis
                formatted_messages = []
                for msg in messages:
                    try:
                        # Parse timestamp
                        timestamp = clean_text(str(msg.get('timestamp', '')))
                        try:
                            dt = isoparse(timestamp)
                        except:
                            continue
                            
                        # Clean and format message content with aggressive cleaning
                        raw_content = msg.get('content', '')
                        # Apply aggressive cleaning twice to ensure all HTML artifacts are removed
                        content = clean_text(clean_text(raw_content))
                        
                        # Create formatted message
                        formatted_msg = {
                            'message_id': msg.get('message_id', f'msg_{len(formatted_messages)}'),
                            'timestamp': dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            'sender': msg.get('sender', 'Unknown'),
                            'recipient': msg.get('recipient', 'Unknown'),
                            'content': content,
                            'datetime': dt
                        }
                        formatted_messages.append(formatted_msg)
                    except Exception as e:
                        continue
            except Exception as e:
                st.error(f"Error processing messages: {str(e)}")
                st.stop()
            
            # Run analysis
            with st.status("Analyzing patterns...", expanded=True) as status:
                # Analyze temporal patterns
                temporal_anomalies = detect_temporal_anomalies(formatted_messages)
                st.session_state.temporal_anomalies = temporal_anomalies
                
                # Analyze contact patterns
                contact_patterns = analyze_contact_patterns(formatted_messages, new_contact_window_hours=24)
                st.session_state.contact_patterns = contact_patterns
                
                # Generate visualizations
                if temporal_anomalies.get("message_spikes"):
                    timeline_html = generate_timeline_html(temporal_anomalies["message_spikes"])
                    st.session_state.timeline_html = timeline_html
                
                if contact_patterns.get("contact_graph"):
                    contact_graph_html = generate_contact_graph_html(contact_patterns["contact_graph"])
                    st.session_state.contact_graph_html = contact_graph_html
                
                # Generate AI suggestions based on behavioral analysis results
                try:
                    gemini_client = GeminiClient()
                    # Create summary data for AI suggestions
                    summary_data = {
                        'total_messages': len(formatted_messages),
                        'odd_hour_count': len(temporal_anomalies.get('odd_hour_messages', [])),
                        'message_spikes_count': len(temporal_anomalies.get('message_spikes', [])),
                        'new_contacts_count': len(contact_patterns.get('new_contacts', [])),
                        'contact_drops_count': len(contact_patterns.get('contact_drops', [])),
                        'has_timeline': bool(temporal_anomalies.get('message_spikes')),
                        'has_contact_graph': bool(contact_patterns.get('contact_graph'))
                    }
                    ai_suggestions = [
                        "Investigate unusual activity during 1-4 AM timeframe" if summary_data['odd_hour_count'] > 0 else None,
                        "Review high-volume messaging periods for coordination patterns" if summary_data['message_spikes_count'] > 0 else None,
                        "Analyze new contacts for suspicious connections" if summary_data['new_contacts_count'] > 0 else None,
                        "Check for contact pattern disruptions indicating operational changes" if summary_data['contact_drops_count'] > 0 else None,
                        "Cross-reference crypto addresses and phone numbers with known databases",
                        "Look for patterns in financial amounts and transaction references",
                        "Analyze messaging frequency changes around key dates"
                    ]
                    # Filter out None values
                    ai_suggestions = [s for s in ai_suggestions if s is not None]
                    st.session_state.ai_suggestions = ai_suggestions
                except Exception as e:
                    st.session_state.ai_suggestions = [
                        "Review temporal patterns for unusual activity",
                        "Investigate contact network changes",
                        "Cross-reference entities with threat intelligence",
                        "Analyze communication frequency patterns"
                    ]
                
                status.update(label="✅ Analysis complete!", state="complete")
    
    # Display Behavioral Analysis Results
    if st.session_state.get("temporal_anomalies"):
        col1, col2 = st.columns([1, 1])
        
        # Column 1: Message Patterns
        with col1:
            with st.expander("⏰ Message Patterns", expanded=True):
                # Show odd hours activity
                odd_hour_messages = st.session_state.temporal_anomalies.get("odd_hour_messages", [])
                if odd_hour_messages:
                    st.subheader("Messages During 1-4 AM")
                    for msg in odd_hour_messages[:5]:
                        with st.container():
                            time_str = msg['datetime'].strftime("%Y-%m-%d %H:%M:%S")
                            st.markdown(f"**{time_str}** · {msg.get('sender', 'Unknown')}")
                            raw_content = msg.get('content', '')
                            # Apply double cleaning to ensure all HTML artifacts are removed
                            content = clean_text(clean_text(raw_content))
                            # Display clean content with inline highlighting (no separate entities section)
                            entities = highlight_entities(content)
                            if entities != content:
                                st.markdown(entities, unsafe_allow_html=True)
                            else:
                                st.text(content)
                            st.markdown("---")
                else:
                    st.info("No unusual hour activity detected.")

        # Column 2: Volume Analysis
        with col2:
            with st.expander("📊 Message Volumes", expanded=True):
                message_spikes = st.session_state.temporal_anomalies.get("message_spikes", [])
                if message_spikes:
                    st.subheader("High Volume Periods")
                    for spike in message_spikes:
                        with st.container():
                            # Handle hour format properly
                            hour_info = spike.get('hour', 'Unknown')
                            if hasattr(hour_info, 'strftime'):
                                hour_display = hour_info.strftime('%Y-%m-%d %H:00')
                            elif isinstance(hour_info, str):
                                hour_display = hour_info
                            else:
                                hour_display = str(hour_info)
                            
                            count = spike.get('count', 0)
                            st.metric(
                                "Time Window", 
                                hour_display,
                                delta=f"+{count} messages",
                                delta_color="normal"
                            )
                else:
                    st.info("No unusual message volumes detected.")
        
        # Full Width: Timeline
        try:
            if hasattr(st.session_state, "timeline_html"):
                st.subheader("Message Timeline")
                components.html(st.session_state.timeline_html, height=400)
        except Exception as e:
            st.error(f"Error displaying timeline: {str(e)}")

        # Message spikes are now handled in the Volume Analysis section above
    
    if hasattr(st.session_state, "contact_patterns"):
        with st.expander("👥 Contact Pattern Analysis", expanded=True):
            # Display new contacts
            if "new_contacts" in st.session_state.contact_patterns and st.session_state.contact_patterns["new_contacts"]:
                st.subheader("New contacts in last 24 hours")
                for contact in st.session_state.contact_patterns["new_contacts"]:
                    with st.expander(f"{contact['sender']} → {contact['recipient']}"):
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.caption("First contact")
                            st.code(contact['first_contact_time'].strftime('%Y-%m-%d %H:%M:%S'))
                        with col2:
                            st.caption("Message count")
                            st.code(str(contact['message_count']))
            else:
                st.info("No new contacts detected in the last 24 hours.")
            
            # Display contact drops
            if "contact_drops" in st.session_state.contact_patterns and st.session_state.contact_patterns["contact_drops"]:
                st.subheader("Sudden drops in usual contacts")
                for drop in st.session_state.contact_patterns["contact_drops"]:
                    st.markdown(f"**Sender:** {drop['sender']}")
                    st.markdown(f"**Recipient:** {drop['recipient']}")
                    st.markdown(f"**Last active:** {drop['last_active']}")
                    st.markdown(f"**Previous message count:** {drop['previous_count']}")
                    st.markdown("---")
            else:
                st.info("No sudden drops in usual contacts detected.")
            
            # Display contact graph visualization
            if hasattr(st.session_state, "contact_graph_html"):
                st.subheader("Contact Network Graph")
                components.html(st.session_state.contact_graph_html, height=700)
    
    if hasattr(st.session_state, "ai_suggestions"):
        with st.expander("💡 AI Investigative Suggestions", expanded=True):
            st.subheader("Suggested next steps")
            for i, suggestion in enumerate(st.session_state.ai_suggestions, 1):
                st.markdown(f"{i}. {suggestion}")

# Forensic Analysis Section
if st.session_state.data_loaded:
    st.subheader("🔍 Forensic Analysis")
    
    # Option to run automated forensic analysis
    if st.button("🔎 Run Automated Forensic Analysis"):
        with st.spinner("Analyzing UFDR data..."):
            # Build the forensics-focused prompt
            forensic_prompt = """
            You are a digital forensics AI assistant.  
            A UFDR (Universal Forensic Data Report) file has been uploaded by the user.  
            Your task is to analyze the contents of this UFDR JSON and generate a clear triage report that highlights: 
            
            - Suspicious or unusual communications  
            - Mentions of crypto wallets, bank details, or financial activity  
            - Foreign or unknown phone numbers  
            - Patterns of repeated contacts, group chats, or coordinated activity  
            - Any red flags useful for investigators  
            
            Return the findings in a structured but concise format (use bullet points or short sections).  
            If the UFDR is very large, prioritize the most relevant and high-risk information instead of summarizing everything.  
            """
            
            # For MVP, we'll use the hybrid search to simulate the analysis
            # In a real implementation, this would call an external  like Gemini
            analysis_queries = [
                "bitcoin",
                "crypto", 
                "wallet",
                "transfer",
                "payment",
                "money",
                "urgent",
                "secret",
                "delete",
                "phone",
                "number",
                "contact"
            ]
            
            all_results = []
            for query in analysis_queries:
                print(f"Running forensic search for: {query}")
                results = hybrid_search(st.session_state.vectorstore, query, top_k=3)
                print(f"Query '{query}' returned {len(results)} results")
                all_results.extend(results)
            
            print(f"Total search results before deduplication: {len(all_results)}")
            
            # Deduplicate results by message_id or content
            unique_results = []
            seen_ids = set()
            seen_content = set()
            
            for doc in all_results:
                msg_id = doc.metadata.get('message_id', '')
                content = doc.page_content.strip()
                
                # Use message_id for deduplication if available, otherwise use content
                if msg_id and msg_id not in seen_ids:
                    unique_results.append(doc)
                    seen_ids.add(msg_id)
                    seen_content.add(content)
                elif not msg_id and content not in seen_content:
                    unique_results.append(doc)
                    seen_content.add(content)
            
            print(f"After deduplication: {len(unique_results)} unique results")
            st.session_state.analysis_results = unique_results
            
            # Display the analysis results
            st.subheader("📊 Forensic Analysis Results")
            st.markdown("### Key Findings from UFDR Analysis")
            
            if unique_results:
                st.success(f"✅ Found {len(unique_results)} items of interest")
                
                # Display results
                for i, doc in enumerate(unique_results, 1):
                    meta = doc.metadata
                    lang_info = f"({meta.get('detected_language', 'en').upper()})" if meta.get('needs_translation') else ""
                    
                    with st.expander(f"Finding #{i} — {meta.get('timestamp', 'N/A')}"):
                        # Get cleaned content from metadata or fallback to aggressive cleaning
                        text_content = meta.get('clean_content')  # Use pre-cleaned content if available
                        if not text_content:
                            # Fallback: extract from page_content and clean aggressively
                            raw_content = meta.get('translated_text', doc.page_content)
                            if raw_content:
                                # Extract just the message part (after "sender: ")
                                parts = raw_content.split(': ', 1)
                                message_only = parts[1] if len(parts) > 1 else raw_content
                                # Apply triple cleaning for heavily corrupted content
                                text_content = clean_text(clean_text(clean_text(message_only)))
                            else:
                                # If no raw_content, use page_content directly
                                text_content = clean_text(doc.page_content)
                        
                        # Always display content if we have any
                        if text_content:
                            # Display content with inline highlighting
                            entities = highlight_entities(text_content)
                            if entities != text_content:
                                st.markdown(entities, unsafe_allow_html=True)
                            else:
                                st.text(text_content)
                        else:
                            st.text(doc.page_content)  # Fallback to raw content
                        
                        # Metadata in a clean format
                        cols = st.columns([2, 1, 1])
                        with cols[0]:
                            st.caption(f"Sender: {meta.get('sender', 'N/A')}")
                        with cols[1]:
                            st.caption(f"Language: {meta.get('detected_language', 'en')}")
                        if meta.get('media_path'):
                            with cols[2]:
                                st.caption(f"Media: {os.path.basename(meta.get('media_path'))}")
                
                # Generate PDF
                if st.button("📥 Export Analysis to PDF"):
                    pdf_path = generate_pdf_report(unique_results, "Automated Forensic Analysis")
                    st.success(f"PDF saved: {pdf_path}")
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Forensic Report",
                            data=f,
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf"
                        )
            else:
                st.warning("No significant findings detected.")
    
    # Manual Query Section
    st.subheader("🔍 Manual Query")
    
    # Initialize session state variables for manual query
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ""
    if 'last_results' not in st.session_state:
        st.session_state.last_results = []
    
    # Query input
    query = st.text_input(
        "Ask in English about the UFDR data",
        placeholder="e.g., 'Show me chats with crypto addresses' or 'Find suspicious activity'",
        key="chat_input"
    )
    
    # Suggestion buttons - each will set and process a specific query
    st.markdown("**Quick suggestions:**")
    col1, col2, col3 = st.columns(3)
    
    suggestion_pressed = None
    with col1:
        if st.button("🔍 Find suspicious activity", key="btn_suspicious"):
            suggestion_pressed = "Show me suspicious or unusual communications"
    with col2:
        if st.button("💰 Check financial activity", key="btn_financial"):
            suggestion_pressed = "Find mentions of crypto wallets or financial transactions"
    with col3:
        if st.button("👥 Analyze contacts", key="btn_contacts"):
            suggestion_pressed = "Show me patterns of repeated contacts or coordinated activity"
    
    # Use suggestion if a button was pressed, otherwise use typed query
    if suggestion_pressed:
        query = suggestion_pressed
    
    # Process query if present
    if query and query.strip():
        current_query = query.strip()
        if not st.session_state.vectorstore:
            st.warning("Please upload UFDR data first before querying.")
        else:
            try:
                with st.spinner("🔍 Searching messages..."):
                    # Store query in history
                    st.session_state.chat_history.append({"role": "user", "content": current_query})
                    
                    # Search and deduplicate results
                    raw_results = hybrid_search(st.session_state.vectorstore, current_query, top_k=10)
                    results = []
                    seen_ids = set()
                    
                    for doc in raw_results:
                        msg_id = doc.metadata.get('message_id', '')
                        if msg_id not in seen_ids:
                            results.append(doc)
                            seen_ids.add(msg_id)
                    
                    # Store results and clean them
                    cleaned_results = []
                    for doc in results:
                        # Clean the content thoroughly
                        if hasattr(doc, 'page_content'):
                            doc.page_content = clean_text(doc.page_content)
                            doc.page_content = re.sub(r'<[^>]+>', '', doc.page_content)
                            doc.page_content = doc.page_content.strip()
                        cleaned_results.append(doc)
                    
                    st.session_state.results = cleaned_results
                    
                    # Display results and add to chat history
                    if cleaned_results:
                        response = f"Found {len(cleaned_results)} matches."
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response
                        })
                    else:
                        st.warning("No matches found for your query. Try rephrasing or using different keywords.")
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": "No relevant matches found."
                        })
            
            except Exception as e:
                st.error(f"Error processing query: {str(e)}")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"Error: {str(e)}"
                })
    
    # Display results if we have them
    if st.session_state.get('results'):
        results = st.session_state.results
        st.success(f"✅ Found {len(results)} relevant matches")
        
        # Show results in clean format
        for i, doc in enumerate(results, 1):
            meta = doc.metadata
            
            # Format timestamp
            timestamp = meta.get('timestamp', '')
            try:
                dt = isoparse(timestamp)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted_time = timestamp if timestamp else 'N/A'
            
            # Use a container for each message
            with st.container():
                header_col1, header_col2 = st.columns([3, 1])
                with header_col1:
                    st.markdown(f"**Message {i}** · {meta.get('sender', 'Unknown')}")
                with header_col2:
                    st.markdown(formatted_time)
                
                # Clean and display message content with inline highlighting
                cleaned = clean_text(doc.page_content)
                entities = highlight_entities(cleaned)
                if entities != cleaned:  # Display with highlighting if entities found
                    st.markdown(entities, unsafe_allow_html=True)
                else:
                    st.text(cleaned)
                
                # Show minimal metadata
                st.caption(f"Language: {meta.get('detected_language', 'en').upper()}")
                
                # Media handling
                if meta.get('media_path'):
                    st.markdown("**Media:**")
                    media_path = meta.get('media_path')
                    # Show image preview for supported formats
                    if any(media_path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                        try:
                            st.image(media_path, caption="Media content")
                        except Exception as e:
                            st.markdown(f"📎 {media_path}")
                            st.caption("Preview not available")
                    else:
                        st.markdown(f"📎 {media_path}")
                
        # Generate PDF export button
        if st.button("📥 Export Search Results to PDF", key="export_search_pdf"):
            try:
                # Check if behavioral analysis has been run
                anomalies_data = None
                ai_suggestions_data = None
                
                if hasattr(st.session_state, "temporal_anomalies") and hasattr(st.session_state, "contact_patterns"):
                    anomalies_data = {
                        **st.session_state.temporal_anomalies,
                        **st.session_state.contact_patterns
                    }
                
                if hasattr(st.session_state, "ai_suggestions"):
                    ai_suggestions_data = st.session_state.ai_suggestions
                
                # Generate PDF with behavioral intelligence data if available
                pdf_path = generate_pdf_report(
                    results, 
                    current_query, 
                    anomalies=anomalies_data,
                    ai_suggestions=ai_suggestions_data
                )
                st.success(f"PDF saved: {pdf_path}")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Report",
                        data=f,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf"
                    )
            except Exception as e:
                st.error(f"Error generating PDF: {str(e)}")

# Demo script note
st.sidebar.header("💡 MVP Demo Script")
st.sidebar.write("""
1. Upload your UFDR JSON or use sample data
2. Run automated forensic analysis
3. Review highlighted findings
4. Or use manual query: "crypto addresses"
5. Export to PDF and download the report!
""")