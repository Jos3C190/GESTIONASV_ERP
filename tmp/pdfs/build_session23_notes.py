from pathlib import Path
import re
from html import escape
from decimal import Decimal, getcontext
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
import json

ROOT = Path(r'C:\Developer\GESTIONASV_ERP')
SOURCE = ROOT / 'output/pdf/Apuntes_Sesion_23_Inventario_y_compras.md'
TARGET = ROOT / 'output/pdf/Apuntes_Sesion_23_Inventario_y_compras.pdf'
FONT = Path(r'C:\Windows\Fonts')
pdfmetrics.registerFont(TTFont('Segoe', str(FONT / 'segoeui.ttf')))
pdfmetrics.registerFont(TTFont('SegoeBold', str(FONT / 'segoeuib.ttf')))
pdfmetrics.registerFont(TTFont('SegoeItalic', str(FONT / 'segoeuii.ttf')))
pdfmetrics.registerFontFamily('Segoe', normal='Segoe', bold='SegoeBold', italic='SegoeItalic', boldItalic='SegoeBold')

INK = colors.HexColor('#172B41')
MUTED = colors.HexColor('#566677')
BLUE = colors.HexColor('#12616E')
LINE = colors.HexColor('#D8E2E8')
PALE = colors.HexColor('#EEF5F7')
W, H = A4
WIDTH = W - 88

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyNote', fontName='Segoe', fontSize=10.5, leading=14.4, textColor=INK, spaceAfter=7))
styles.add(ParagraphStyle(name='MainTitle', fontName='SegoeBold', fontSize=25, leading=30, textColor=INK, spaceAfter=12))
styles.add(ParagraphStyle(name='Chapter', fontName='SegoeBold', fontSize=20, leading=24, textColor=INK, spaceAfter=12, keepWithNext=True))
styles.add(ParagraphStyle(name='SubtitleNote', fontName='Segoe', fontSize=16, leading=21, textColor=BLUE, spaceAfter=12, keepWithNext=True))
styles.add(ParagraphStyle(name='SubheadNote', fontName='SegoeBold', fontSize=11.2, leading=15, textColor=BLUE, spaceBefore=7, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name='BulletNote', parent=styles['BodyNote'], leftIndent=11, firstLineIndent=-8, spaceAfter=4))
styles.add(ParagraphStyle(name='TableNote', fontName='Segoe', fontSize=9.1, leading=12.2, textColor=INK))
styles.add(ParagraphStyle(name='TableHeadNote', fontName='SegoeBold', fontSize=9.1, leading=12.2, textColor=colors.white))
styles.add(ParagraphStyle(name='SourceNote', fontName='SegoeItalic', fontSize=8, leading=11, textColor=MUTED, spaceBefore=5, spaceAfter=4))
styles.add(ParagraphStyle(name='CalloutNote', fontName='Segoe', fontSize=10, leading=14, textColor=INK))

def rich(text):
    text = escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    return text

def para(text, kind='BodyNote'):
    return Paragraph(rich(text), styles[kind])

def build_table(lines):
    rows = [[x.strip() for x in line.strip().strip('|').split('|')] for line in lines]
    rows = [r for r in rows if not all(re.fullmatch(r'[:\- ]+', x) for x in r)]
    n = len(rows[0])
    if n == 2:
        fractions = [0.33, 0.67]
    elif n == 3:
        fractions = [0.22, 0.39, 0.39]
        if rows[0][0] == 'ID / prioridad':
            fractions = [0.14, 0.25, 0.61]
    elif n == 4:
        fractions = [0.39, 0.24, 0.23, 0.14]
    else:
        fractions = [1/n] * n
    data = [[para(cell, 'TableHeadNote' if i == 0 else 'TableNote') for cell in row] for i, row in enumerate(rows)]
    table = Table(data, colWidths=[WIDTH*f for f in fractions], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 1), (-1, -1), 0.35, LINE),
    ]))
    return [table, Spacer(1, 8)]

def parse_section(text, first=False):
    lines = text.strip().splitlines()
    flow = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('|'):
            tbl = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                tbl.append(lines[i]); i += 1
            flow.extend(build_table(tbl))
            continue
        if line.startswith('# '):
            flow.append(para(line[2:], 'MainTitle' if first else 'Chapter'))
        elif line.startswith('## '):
            flow.append(para(line[3:], 'SubtitleNote'))
        elif line.startswith('### '):
            flow.append(para(line[4:], 'SubheadNote'))
        elif line.startswith('> '):
            callout = Table([[para(line[2:], 'CalloutNote')]], colWidths=[WIDTH])
            callout.setStyle(TableStyle([
                ('BACKGROUND', (0,0),(-1,-1),PALE),
                ('LINEBEFORE',(0,0),(0,-1),3,BLUE),
                ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),
                ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
            ]))
            flow.extend([callout,Spacer(1,9)])
        elif line.startswith('- '):
            flow.append(para('• ' + line[2:], 'BulletNote'))
        elif re.match(r'^\d+\. ', line):
            flow.append(para(line, 'BulletNote'))
        elif line.startswith(('Base del TXT:', 'Base conceptual:', 'Fuente:')):
            flow.append(para(line, 'SourceNote'))
        else:
            flow.append(para(line))
        i += 1
    return flow

def decorate(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(44, H-39, W-44, H-39)
    canvas.setFont('SegoeBold', 8)
    canvas.setFillColor(BLUE)
    canvas.drawString(44, H-29, 'APUNTES DE CLASE / SISTEMA ERP')
    canvas.setFont('Segoe', 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(W-44, H-29, 'SESIÓN 23 · 12 OCT 2026')
    canvas.line(44, 36, W-44, 36)
    canvas.setFont('Segoe', 7.5)
    canvas.drawString(44, 23, 'Inventario y compras · Explicación, requisitos y decisiones pendientes')
    canvas.drawRightString(W-44, 23, str(doc.page))
    canvas.restoreState()

raw = SOURCE.read_text(encoding='utf-8')
sections = raw.split('<!-- page -->')
story = []
for i, section in enumerate(sections):
    if i:
        story.append(PageBreak())
    story.extend(parse_section(section, first=(i==0)))

doc = SimpleDocTemplate(str(TARGET), pagesize=A4, leftMargin=44, rightMargin=44, topMargin=53, bottomMargin=49,
    title='Apuntes de la sesión 23 - Inventario y compras', author='Apuntes preparados a partir de la transcripción aportada',
    subject='Recepción, retaceo, viñeteado, ubicación, costo promedio y kardex')
doc.build(story, onFirstPage=decorate, onLaterPages=decorate)

reader = PdfReader(str(TARGET))
page_summary = []
for i, page in enumerate(reader.pages):
    text = page.extract_text() or ''
    page_summary.append({'page': i+1, 'characters': len(text), 'first_text': text.splitlines()[4:7]})
getcontext().prec=28
avg = (Decimal(10)*10 + Decimal(8)*12)/18
assert Decimal(10)*10+Decimal(2)*12 == 124
assert avg*12 + avg*6 == Decimal(196)
report = {'pdf':str(TARGET),'pages':len(reader.pages),'expected_sections':len(sections),'words':len(raw.split()),
          'example':{'average':str(avg),'out':str(avg*12),'remaining':str(avg*6)},'page_summary':page_summary}
(ROOT/'tmp/pdfs/session23_build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
