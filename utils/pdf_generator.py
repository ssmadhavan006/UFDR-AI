# utils/pdf_generator.py
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime
import os

def generate_pdf_report(matches: list, query: str, output_path: str = "reports/", anomalies: dict = None, ai_suggestions: list = None):
    """Generate PDF report with highlighted matches and optional behavioral analytics data"""
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    filename = f"forensis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_path, filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom style for highlighted text
    highlighted_style = ParagraphStyle(
        'Highlighted',
        parent=styles['Normal'],
        textColor=colors.red,
        fontName='Helvetica-Bold'
    )
    
    story = []
    
    # Cover
    story.append(Paragraph("Case Summary — FORENSIS-AI", styles['Title']))
    story.append(Spacer(1, 24))
    story.append(Paragraph(f"Query: {query}", styles['Heading2']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Italic']))
    story.append(Spacer(1, 36))
    
    # Behavioral Anomalies
    if anomalies:
        story.append(Paragraph("Behavioral Intelligence Findings", styles['Heading1']))
        story.append(Spacer(1, 12))
        
        # Odd Hour Activity
        odd_hours = anomalies.get("odd_hour_messages", [])
        if odd_hours:
            story.append(Paragraph(f"Odd-Hour Activity (1-4 AM): {len(odd_hours)} messages detected", styles['Heading2']))
            story.append(Spacer(1, 6))
            for i, msg in enumerate(odd_hours[:5], 1):
                clean_msg = msg.get('content', '')
                story.append(Paragraph(f"{i}. [{msg.get('timestamp')}] {msg.get('sender')}: {clean_msg}", styles['Normal']))
            story.append(Spacer(1, 12))
            
        # Message spikes
        spikes = anomalies.get("message_spikes", [])
        if spikes:
            story.append(Paragraph("High Volume Spikes:", styles['Heading2']))
            story.append(Spacer(1, 6))
            for spike in spikes:
                story.append(Paragraph(f"• {spike.get('hour')}: {spike.get('count')} messages", styles['Normal']))
            story.append(Spacer(1, 12))
            
        # New Contacts
        new_contacts = anomalies.get("new_contacts", [])
        if new_contacts:
            story.append(Paragraph("New Contacts Established (last 24h):", styles['Heading2']))
            story.append(Spacer(1, 6))
            for contact in new_contacts:
                story.append(Paragraph(f"• {contact.get('sender')} &rarr; {contact.get('recipient')} (First contact: {contact.get('first_contact_time')})", styles['Normal']))
            story.append(Spacer(1, 12))
            
        # Contact Drops
        contact_drops = anomalies.get("contact_drops", [])
        if contact_drops:
            story.append(Paragraph("Sudden Drops in Contact Frequency:", styles['Heading2']))
            story.append(Spacer(1, 6))
            for drop in contact_drops:
                story.append(Paragraph(f"• {drop.get('sender')} &rarr; {drop.get('recipient')} (Last active: {drop.get('last_active')}, Prev count: {drop.get('previous_count')})", styles['Normal']))
            story.append(Spacer(1, 12))
            
        story.append(Spacer(1, 12))
        
    # AI Investigative Suggestions
    if ai_suggestions:
        story.append(Paragraph("AI Investigative Suggestions", styles['Heading1']))
        story.append(Spacer(1, 12))
        for i, sug in enumerate(ai_suggestions, 1):
            story.append(Paragraph(f"{i}. {sug}", styles['Normal']))
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 24))
    
    # Results
    story.append(Paragraph("Top Matching Messages", styles['Heading1']))
    story.append(Spacer(1, 12))
    
    for i, doc_obj in enumerate(matches[:10], 1):
        content = doc_obj.page_content
        p_text = f"{i}. {content}"
        story.append(Paragraph(p_text, styles['Normal']))
        story.append(Spacer(1, 6))
        
        # Add metadata
        meta = doc_obj.metadata
        story.append(Paragraph(f"Timestamp: {meta.get('timestamp', 'N/A')} | Sender: {meta.get('sender', 'N/A')}", styles['Italic']))
        if meta.get('media_path'):
            story.append(Paragraph(f"Media: {meta.get('media_path')}", styles['Italic']))
        story.append(Spacer(1, 12))
    
    doc.build(story)
    return filepath