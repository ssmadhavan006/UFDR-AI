# utils/pdf_generator.py
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime
import os

def generate_pdf_report(matches: list, query: str, output_path: str = "reports/"):
    """Generate PDF report with highlighted matches"""
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
    
    # Results
    story.append(Paragraph("Top Matching Messages", styles['Heading1']))
    story.append(Spacer(1, 12))
    
    for i, doc in enumerate(matches[:10], 1):
        content = doc.page_content
        # Simple highlight: wrap **text** in red
        # In real PDF, you’d parse Markdown → styled spans
        # MVP: Just show raw with note
        p_text = f"{i}. {content} [Highlighted entities in red in interactive view]"
        story.append(Paragraph(p_text, styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Add metadata
        meta = doc.metadata
        story.append(Paragraph(f"Timestamp: {meta.get('timestamp', 'N/A')}", styles['Italic']))
        story.append(Paragraph(f"Sender: {meta.get('sender', 'N/A')}", styles['Italic']))
        if meta.get('media_path'):
            story.append(Paragraph(f"Media: {meta.get('media_path')}", styles['Italic']))
        story.append(Spacer(1, 24))
    
    doc.build(story)
    return filepath