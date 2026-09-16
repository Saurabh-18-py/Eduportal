import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)
from django.core.files.base import ContentFile

# Same palette as static/css/style.css - keep these two in sync if the site theme changes.
INK = colors.HexColor('#1B1B3A')
INK_SOFT = colors.HexColor('#4A4A68')
PAPER = colors.HexColor('#FAF6EC')
RULE = colors.HexColor('#DCD3BF')
RED = colors.HexColor('#C1443C')
TEAL = colors.HexColor('#1F7A6C')
GOLD = colors.HexColor('#C99A2E')


def _escape(text):
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _draw_page_frame(canvas, doc, subject_name, chapter, class_level):
    """Runs on every page: cream background, header strip, footer, page number."""
    canvas.saveState()
    width, height = A4

    # Cream page background
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    # Header strip
    canvas.setFillColor(INK)
    canvas.rect(0, height - 1.6 * cm, width, 1.6 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(2 * cm, height - 1.05 * cm, "EDUPORTAL")
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(
        width - 2 * cm, height - 1.05 * cm,
        f"Class {class_level}  |  {subject_name}"
    )
    # Thin gold rule under header
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1.2)
    canvas.line(0, height - 1.6 * cm, width, height - 1.6 * cm)

    # Footer
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.7)
    canvas.line(2 * cm, 1.3 * cm, width - 2 * cm, 1.3 * cm)
    canvas.setFillColor(INK_SOFT)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(2 * cm, 0.9 * cm, _escape(chapter)[:70])
    canvas.drawRightString(width - 2 * cm, 0.9 * cm, f"Page {doc.page}")

    canvas.restoreState()


def build_notes_pdf(subject_name, chapter, class_level, sections):
    """
    sections: list of {'heading': str, 'content': str}. Returns a Django
    ContentFile ready to assign to a FileField. Styled to match the site's
    Hall Ticket / Admit Card theme (indigo + cream + vermilion + gold).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2.4 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title=f"{chapter} - Class {class_level} {subject_name} Notes",
    )

    styles = getSampleStyleSheet()

    eyebrow_style = ParagraphStyle(
        'Eyebrow', parent=styles['Normal'], fontSize=10, textColor=RED,
        fontName='Helvetica-Bold', spaceAfter=4,
    )
    title_style = ParagraphStyle(
        'NotesTitle', parent=styles['Title'], fontSize=24, leading=28,
        textColor=INK, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        'NotesMeta', parent=styles['Normal'], fontSize=10.5, textColor=INK_SOFT,
        alignment=TA_CENTER, spaceAfter=0,
    )
    heading_style = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'], fontSize=13.5, spaceBefore=16, spaceAfter=8,
        textColor=colors.white, fontName='Helvetica-Bold', leading=16,
    )
    body_style = ParagraphStyle(
        'SectionBody', parent=styles['Normal'], fontSize=10.5, leading=15.5, spaceAfter=7,
        textColor=INK,
    )

    # --- Cover block: eyebrow + title + meta line, boxed like an admit card ---
    cover_inner = [
        [Paragraph("CHAPTER NOTES", eyebrow_style)],
        [Paragraph(_escape(chapter), title_style)],
        [Paragraph(f"Class {class_level} &nbsp;&middot;&nbsp; {_escape(subject_name)} &nbsp;&middot;&nbsp; CBSE", meta_style)],
    ]
    cover_table = Table(cover_inner, colWidths=[doc.width])
    cover_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, GOLD),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))

    story = [cover_table, Spacer(1, 18)]

    for section in sections:
        heading_bar = Table(
            [[Paragraph(_escape(section['heading']), heading_style)]],
            colWidths=[doc.width],
        )
        heading_bar.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), TEAL),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        body_paras = []
        for para in section['content'].split('\n'):
            para = para.strip()
            if para:
                body_paras.append(Paragraph(_escape(para), body_style))

        # Keep a section's heading with at least its first paragraph so a
        # heading never ends up alone at the bottom of a page.
        story.append(KeepTogether([heading_bar, Spacer(1, 6)] + body_paras[:1]))
        story.extend(body_paras[1:])
        story.append(Spacer(1, 4))

    doc.build(
        story,
        onFirstPage=lambda c, d: _draw_page_frame(c, d, subject_name, chapter, class_level),
        onLaterPages=lambda c, d: _draw_page_frame(c, d, subject_name, chapter, class_level),
    )
    buffer.seek(0)
    filename = f"{subject_name}_{chapter}_notes.pdf".replace(' ', '_').replace('/', '-')
    return ContentFile(buffer.read(), name=filename)
