from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

PAGE_W, PAGE_H = landscape((29.7 * cm, 16.7 * cm))

NAVY = colors.HexColor('#0d2340')
DARKBG = colors.HexColor('#12141c')
GOLD = colors.HexColor('#f5d547')
PINK = colors.HexColor('#ec4899')
YELLOW = colors.HexColor('#fde047')
WHITE = colors.white
GREY_LINE = colors.HexColor('#3a5a85')
CYAN = colors.HexColor('#5ee6d0')
RED = colors.HexColor('#e74c3c')


def _bg(c, color=NAVY):
    c.setFillColor(color)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def _title(c, text, x, y, size=28, color=GOLD):
    c.setFont("Helvetica-Bold", size)
    c.setFillColor(color)
    c.drawString(x, y, text)
    w = c.stringWidth(text, "Helvetica-Bold", size)
    c.setStrokeColor(color)
    c.setLineWidth(2)
    c.line(x, y - 6, x + w, y - 6)


def _bullets(c, items, x, y, max_width, size=13, leading=17.5, color=WHITE, bullet_color=CYAN):
    c.setFont("Helvetica-Bold", size)
    for item in items:
        lines = simpleSplit(str(item), "Helvetica-Bold", size, max_width)
        c.setFillColor(bullet_color)
        c.circle(x - 14, y - 5, 3, fill=1, stroke=0)
        c.setFillColor(color)
        for line in lines:
            if y < 1.5 * cm:
                break
            c.drawString(x, y, line)
            y -= leading
        y -= 4
    return y


def _footer(c, chnum, chname):
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    label = f"Class {chnum[0]}  |  Ch: {chname}" if False else chname
    c.drawRightString(PAGE_W - 30, 20, chname)


def _table(c, headers, rows, x, y, col_w, row_h=1.5):
    row_h = row_h * cm
    c.setFillColor(colors.HexColor('#1a3a63'))
    c.rect(x, y - row_h, sum(col_w), row_h, fill=1, stroke=0)
    xc = x
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(CYAN)
    for h, w in zip(headers, col_w):
        for i, line in enumerate(simpleSplit(str(h), "Helvetica-Bold", 12, w - 16)):
            c.drawString(xc + 8, y - row_h + 12 + (len(simpleSplit(str(h), "Helvetica-Bold", 12, w-16))-1-i)*13, line)
        xc += w
    ty = y - row_h
    for r in rows:
        max_lines = 1
        wrapped_cells = []
        for val, w in zip(r, col_w):
            lines = simpleSplit(str(val), "Helvetica-Bold", 10.5, w - 16)
            wrapped_cells.append(lines)
            max_lines = max(max_lines, len(lines))
        this_row_h = max(row_h, (max_lines * 13 + 14))
        ty -= this_row_h
        c.setFillColor(colors.HexColor('#16294a'))
        c.rect(x, ty, sum(col_w), this_row_h, fill=1, stroke=0)
        c.setStrokeColor(GREY_LINE)
        c.rect(x, ty, sum(col_w), this_row_h, fill=0, stroke=1)
        xc = x
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(WHITE)
        for lines, w in zip(wrapped_cells, col_w):
            ly = ty + this_row_h - 16
            for line in lines:
                c.drawString(xc + 8, ly, line)
                ly -= 13
            xc += w
    return ty


def _pyq_box(c, years, question, options, x, y, w):
    lines_q = simpleSplit(question, "Helvetica-Bold", 14, w - 40)
    opt_lines = []
    if options:
        for opt in options:
            opt_lines.extend(simpleSplit(str(opt), "Helvetica-Bold", 13, w - 40))
    h = 1.3 * cm + len(lines_q) * 0.55 * cm + len(opt_lines) * 0.5 * cm + 0.6 * cm
    c.setFillColor(DARKBG)
    c.setStrokeColor(YELLOW)
    c.setLineWidth(2)
    c.roundRect(x, y - h, w, h, 12, fill=1, stroke=1)
    ty = y - 32
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(PINK)
    for line in simpleSplit(years, "Helvetica-Bold", 14, w - 40):
        c.drawString(x + 20, ty, line)
        ty -= 19
    ty -= 6
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(YELLOW)
    for line in lines_q:
        c.drawString(x + 20, ty, line)
        ty -= 19
    if options:
        ty -= 4
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(YELLOW)
        for line in opt_lines:
            c.drawString(x + 20, ty, line)
            ty -= 18
    return y - h


def build_notes_pdf(data, output_path, class_level, subject_name, chapter_name):
    """data: dict matching the schema from notes_ai_helpers.build_notes_prompt"""
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    footer_label = f"Class {class_level} {subject_name} | {chapter_name}"

    # Title slide
    _bg(c, NAVY)
    c.setFillColor(GOLD)
    c.roundRect(3 * cm, PAGE_H - 4.3 * cm, 9 * cm, 1.3 * cm, 8, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(WHITE)
    c.drawCentredString(3 * cm + 4.5 * cm, PAGE_H - 4 * cm, f"CLASS {class_level}  \u2022  {subject_name.upper()}")
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(WHITE)
    title_lines = simpleSplit(data.get('title', chapter_name).upper(), "Helvetica-Bold", 32, 24 * cm)
    ty = PAGE_H - 6.5 * cm
    for line in title_lines:
        c.drawString(3 * cm, ty, line)
        ty -= 1.1 * cm
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(CYAN)
    c.drawString(3 * cm, ty - 0.5 * cm, data.get('tagline', ''))
    c.showPage()

    # Section slides
    for section in data.get('sections', []):
        _bg(c, NAVY)
        _title(c, section.get('heading', '').upper(), 2.5 * cm, PAGE_H - 2.2 * cm)
        y = PAGE_H - 3.6 * cm

        formula = section.get('formula')
        if formula:
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(WHITE)
            for line in simpleSplit(str(formula), "Helvetica-Bold", 16, 24 * cm):
                c.drawCentredString(PAGE_W / 2, y, line)
                y -= 0.7 * cm
            y -= 0.4 * cm

        bullets = section.get('bullets') or []
        if bullets:
            # If too many bullets to fit, split across continuation slides
            remaining = list(bullets)
            first = True
            while remaining:
                if not first:
                    _bg(c, NAVY)
                    _title(c, (section.get('heading', '') + " (cont.)").upper(), 2.5 * cm, PAGE_H - 2.2 * cm)
                    y = PAGE_H - 3.6 * cm
                # estimate how many bullets fit in remaining vertical space
                fit = []
                test_y = y
                min_y = 3.2 * cm if not section.get('table') else 6 * cm
                for b in remaining:
                    lines_needed = len(simpleSplit(str(b), "Helvetica-Bold", 13, 24 * cm))
                    space_needed = lines_needed * 17.5 + 4
                    if test_y - space_needed < min_y and fit:
                        break
                    test_y -= space_needed
                    fit.append(b)
                y = _bullets(c, fit, 2.9 * cm, y, 24 * cm)
                remaining = remaining[len(fit):]
                if remaining:
                    _footer(c, class_level, footer_label)
                    c.showPage()
                first = False

        table = section.get('table')
        if table and table.get('headers') and table.get('rows'):
            headers = table['headers']
            n = len(headers)
            col_w = [24 * cm / n] * n
            _table(c, headers, table['rows'], 2.5 * cm, y - 0.2 * cm, col_w)

        _footer(c, class_level, footer_label)
        c.showPage()

    # PYQ slides
    for pyq in data.get('pyqs', []):
        _bg(c, colors.HexColor('#0a0a0f'))
        _pyq_box(c, pyq.get('years', 'CBSE Board Question'), pyq.get('question', ''),
                  pyq.get('options'), 2.5 * cm, PAGE_H - 1.5 * cm, 24 * cm)
        _footer(c, class_level, footer_label)
        c.showPage()

    # Revision slide
    if data.get('revision_points'):
        _bg(c, NAVY)
        _title(c, "QUICK REVISION", 2.5 * cm, PAGE_H - 2.2 * cm)
        _bullets(c, data['revision_points'], 2.9 * cm, PAGE_H - 3.6 * cm, 24 * cm,
                  bullet_color=GOLD)
        _footer(c, class_level, footer_label)
        c.showPage()

    # Common mistakes slide
    if data.get('common_mistakes'):
        _bg(c, NAVY)
        _title(c, "COMMON MISTAKES", 2.5 * cm, PAGE_H - 2.2 * cm)
        _bullets(c, data['common_mistakes'], 2.9 * cm, PAGE_H - 3.6 * cm, 24 * cm,
                  bullet_color=RED)
        _footer(c, class_level, footer_label)
        c.showPage()

    c.save()
