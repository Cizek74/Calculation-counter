import csv
import re
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from pdf_fonts import _FONT_REG, _FONT_BOLD, _FONT_MONO, _PDF_FONTS_OK


def save_to_csv(data, filename):
    """Save data to CSV"""
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            if data:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
        return True
    except Exception as e:
        print(f"Error saving CSV: {str(e)}")
        return False


def create_invoice_format(all_invoice_data):
    """Create invoice format with each printer as column"""
    customer_data = {}

    for record in all_invoice_data:
        customer_key = record['Customer']
        printer_id = f"{record['Printer_Model']}_{record['Serial_Number']}"

        if customer_key not in customer_data:
            customer_data[customer_key] = {
                'customer': customer_key,
                'date_range': record['Date_Range'],
                'printers': {}
            }

        customer_data[customer_key]['printers'][printer_id] = {
            'model': record['Printer_Model'],
            'serial': record['Serial_Number'],
            'bw_billable': record['Billable_BW_Pages'],
            'color_billable': record['Billable_Color_Pages'],
            'total_billable': record['Total_Billable_Pages']
        }

    invoice_rows = []

    for customer_key, data in customer_data.items():
        printer_ids = list(data['printers'].keys())

        base_row = {
            'Customer': customer_key,
            'Date_Range': data['date_range'],
            'Total_Printers': len(printer_ids)
        }

        rows_data = {
            'Printer_Models': base_row.copy(),
            'Serial_Numbers': base_row.copy(),
            'BW_Billable_Pages': base_row.copy(),
            'Color_Billable_Pages': base_row.copy(),
            'Total_Billable_Pages': base_row.copy()
        }

        rows_data['Printer_Models']['Metric'] = 'Printer_Model'
        rows_data['Serial_Numbers']['Metric'] = 'Serial_Number'
        rows_data['BW_Billable_Pages']['Metric'] = 'BW_Billable_Pages'
        rows_data['Color_Billable_Pages']['Metric'] = 'Color_Billable_Pages'
        rows_data['Total_Billable_Pages']['Metric'] = 'Total_Billable_Pages'

        for i, printer_id in enumerate(printer_ids, 1):
            printer = data['printers'][printer_id]
            col_name = f'Printer_{i}'

            rows_data['Printer_Models'][col_name] = printer['model']
            rows_data['Serial_Numbers'][col_name] = printer['serial']
            rows_data['BW_Billable_Pages'][col_name] = printer['bw_billable']
            rows_data['Color_Billable_Pages'][col_name] = printer['color_billable']
            rows_data['Total_Billable_Pages'][col_name] = printer['total_billable']

        total_bw = sum(p['bw_billable'] for p in data['printers'].values())
        total_color = sum(p['color_billable'] for p in data['printers'].values())
        total_all = sum(p['total_billable'] for p in data['printers'].values())

        rows_data['Printer_Models']['Total'] = 'ALL_PRINTERS'
        rows_data['Serial_Numbers']['Total'] = 'TOTALS'
        rows_data['BW_Billable_Pages']['Total'] = total_bw
        rows_data['Color_Billable_Pages']['Total'] = total_color
        rows_data['Total_Billable_Pages']['Total'] = total_all

        for row_type, row_data in rows_data.items():
            invoice_rows.append(row_data)

        invoice_rows.append({'Customer': '', 'Metric': '--- SEPARATOR ---'})

    return invoice_rows


def generate_summary(all_invoice_data):
    """Generate summary with separate locations"""
    customer_summaries = {}

    for record in all_invoice_data:
        customer_key = record['Customer']

        if customer_key not in customer_summaries:
            customer_summaries[customer_key] = {
                'customer': customer_key,
                'date_range': record['Date_Range'],
                'printers': 0,
                'total_bw_billable': 0,
                'total_color_billable': 0,
                'total_billable': 0,
                'machines': []
            }

        customer_summaries[customer_key]['printers'] += 1
        customer_summaries[customer_key]['total_bw_billable'] += record['Billable_BW_Pages']
        customer_summaries[customer_key]['total_color_billable'] += record['Billable_Color_Pages']
        customer_summaries[customer_key]['total_billable'] += record['Total_Billable_Pages']
        customer_summaries[customer_key]['machines'].append({
            'model': record['Printer_Model'],
            'serial': record['Serial_Number'],
            'bw_billable': record['Billable_BW_Pages'],
            'color_billable': record['Billable_Color_Pages'],
            'total_billable': record['Total_Billable_Pages']
        })

    customer_list = list(customer_summaries.values())

    overall = {
        'total_customers': len(customer_list),
        'total_printers': sum(c['printers'] for c in customer_list),
        'total_bw_all': sum(c['total_bw_billable'] for c in customer_list),
        'total_color_all': sum(c['total_color_billable'] for c in customer_list),
        'total_billable_all': sum(c['total_billable'] for c in customer_list),
        'customer_details': customer_list,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    return overall


def generate_pdf_report(summary_data, filename):
    """Generate dark-themed PDF report matching the glassmorphism dashboard UI"""

    # ── Colour palette — mirrors the dark UI exactly ──────────────────────
    PAGE_BG     = colors.HexColor('#0d1130')   # main page background
    CARD_BG     = colors.HexColor('#131835')   # card / table header bg
    CARD_ALT    = colors.HexColor('#0f1428')   # alternating table row
    CARD_RAISED = colors.HexColor('#171d3f')   # slightly elevated card
    BORDER      = colors.HexColor('#1e2550')   # subtle border
    BORDER_LT   = colors.HexColor('#272e60')   # lighter border

    INDIGO      = colors.HexColor('#6366f1')   # primary accent
    VIOLET      = colors.HexColor('#8b5cf6')   # secondary accent

    # Stat card tinted backgrounds + borders
    SC_VI_BG  = colors.HexColor('#1c1d4a')
    SC_VI_BD  = colors.HexColor('#3c3e8a')
    SC_BL_BG  = colors.HexColor('#152040')
    SC_BL_BD  = colors.HexColor('#1a3a6a')
    SC_GR_BG  = colors.HexColor('#0d2318')
    SC_GR_BD  = colors.HexColor('#155224')
    SC_AM_BG  = colors.HexColor('#231700')
    SC_AM_BD  = colors.HexColor('#6b3a00')

    # Text
    TEXT_HI     = colors.HexColor('#e2e8f0')
    TEXT_MD     = colors.HexColor('#6b7296')
    TEXT_LO     = colors.HexColor('#363b5e')

    # Stat card value colours
    VAL_VI      = colors.HexColor('#a5b4fc')
    VAL_BL      = colors.HexColor('#93c5fd')
    VAL_GR      = colors.HexColor('#4ade80')
    VAL_AM      = colors.HexColor('#fbbf24')

    # Contract status colours
    COL_GREEN   = '#4ade80'
    COL_YELLOW  = '#facc15'
    COL_ORANGE  = '#fb923c'
    COL_RED     = '#f87171'
    COL_DIM     = '#363b5e'

    def fmt(n):
        """Czech thousands separator (non-breaking space)."""
        return f"{n:,}".replace(',', '\u00a0')

    buffer = BytesIO()

    # ── Page callback — draws dark background + footer on every page ──────
    def draw_page(canvas, doc):
        canvas.saveState()
        # Dark page background
        canvas.setFillColor(PAGE_BG)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        # Thin footer separator line
        canvas.setStrokeColor(BORDER_LT)
        canvas.setLineWidth(0.4)
        canvas.line(0.55 * inch, 0.52 * inch, A4[0] - 0.55 * inch, 0.52 * inch)
        # Footer text
        canvas.setFont(_FONT_REG, 7)
        canvas.setFillColor(TEXT_LO)
        canvas.drawString(
            0.55 * inch, 0.32 * inch,
            f"Printing Volume Report  \u00b7  Vygenerováno: {summary_data['generated_at']}"
        )
        canvas.drawRightString(
            A4[0] - 0.55 * inch, 0.32 * inch,
            f"Strana {doc.page}"
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=0.55 * inch, bottomMargin=0.65 * inch,
        leftMargin=0.55 * inch, rightMargin=0.55 * inch
    )

    PW = A4[0] - 1.1 * inch   # usable page width ≈ 7.17 in

    story = []

    # ── Paragraph styles ──────────────────────────────────────────────────
    st_hdr_title = ParagraphStyle('HT',   fontName=_FONT_BOLD, fontSize=17,
                                  textColor=TEXT_HI, spaceAfter=4)
    st_hdr_sub   = ParagraphStyle('HS',   fontName=_FONT_REG,  fontSize=8,
                                  textColor=TEXT_MD)
    st_hdr_date  = ParagraphStyle('HD',   fontName=_FONT_REG,  fontSize=8,
                                  textColor=TEXT_MD, alignment=TA_RIGHT)

    st_lbl_vi = ParagraphStyle('LV', fontName=_FONT_BOLD, fontSize=7,
                               textColor=TEXT_MD, spaceAfter=4)
    st_val_vi = ParagraphStyle('VV', fontName=_FONT_BOLD, fontSize=20, textColor=VAL_VI)
    st_val_bl = ParagraphStyle('VB', fontName=_FONT_BOLD, fontSize=20, textColor=VAL_BL)
    st_val_gr = ParagraphStyle('VG', fontName=_FONT_BOLD, fontSize=20, textColor=VAL_GR)
    st_val_am = ParagraphStyle('VA', fontName=_FONT_BOLD, fontSize=20, textColor=VAL_AM)

    st_sect   = ParagraphStyle('SC',   fontName=_FONT_BOLD, fontSize=10,
                               textColor=TEXT_HI, spaceBefore=14, spaceAfter=8)
    st_cname  = ParagraphStyle('CN',   fontName=_FONT_BOLD, fontSize=11,
                               textColor=TEXT_HI)
    st_date   = ParagraphStyle('DT',   fontName=_FONT_REG,  fontSize=8,
                               textColor=TEXT_MD, alignment=TA_RIGHT)

    st_th     = ParagraphStyle('TH',   fontName=_FONT_BOLD, fontSize=8,
                               textColor=TEXT_MD)
    st_th_r   = ParagraphStyle('THR',  fontName=_FONT_BOLD, fontSize=8,
                               textColor=TEXT_MD, alignment=TA_RIGHT)
    st_td     = ParagraphStyle('TD',   fontName=_FONT_REG,  fontSize=10,
                               textColor=TEXT_HI)
    st_td_r   = ParagraphStyle('TDR',  fontName=_FONT_REG,  fontSize=10,
                               textColor=TEXT_HI, alignment=TA_RIGHT)
    st_td_b_r = ParagraphStyle('TDBR', fontName=_FONT_BOLD, fontSize=10,
                               textColor=TEXT_HI, alignment=TA_RIGHT)
    st_mono   = ParagraphStyle('MN',   fontName=_FONT_MONO, fontSize=9,
                               textColor=TEXT_MD)
    st_cs_lbl    = ParagraphStyle('CSL',  fontName=_FONT_BOLD, fontSize=7,
                                  textColor=TEXT_MD, spaceAfter=3)
    st_cs_val    = ParagraphStyle('CSV',  fontName=_FONT_BOLD, fontSize=15,
                                  textColor=TEXT_HI)
    st_cs_val_am = ParagraphStyle('CSVA', fontName=_FONT_BOLD, fontSize=15,
                                  textColor=VAL_AM)

    # ── 1. Header bar ─────────────────────────────────────────────────────
    # Indigo accent strip | title + subtitle | date (right)
    header_table = Table(
        [['',
          [Paragraph('Printing Volume Report', st_hdr_title),
           Paragraph('Přehled tiskových objemů', st_hdr_sub)],
          Paragraph(summary_data['generated_at'], st_hdr_date)]],
        colWidths=[0.06 * inch, PW * 0.62, PW * 0.32]
    )
    header_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, -1),  INDIGO),
        ('BACKGROUND',    (1, 0), (-1, -1), CARD_BG),
        ('TOPPADDING',    (0, 0), (-1, -1), 16),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ('LEFTPADDING',   (0, 0), (0, -1),  0),
        ('RIGHTPADDING',  (0, 0), (0, -1),  0),
        ('LEFTPADDING',   (1, 0), (1, -1),  14),
        ('RIGHTPADDING',  (2, 0), (2, -1),  14),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.16 * inch))

    # ── 2. Summary stat cards (4 tinted cards) ────────────────────────────
    card_configs = [
        (SC_VI_BG, SC_VI_BD, st_lbl_vi, st_val_vi,
         'ZÁKAZNÍCI',       str(summary_data['total_customers'])),
        (SC_BL_BG, SC_BL_BD, st_lbl_vi, st_val_bl,
         'TISKÁRNY',        str(summary_data['total_printers'])),
        (SC_GR_BG, SC_GR_BD, st_lbl_vi, st_val_gr,
         'ČB STRÁNKY',      fmt(summary_data['total_bw_all'])),
        (SC_AM_BG, SC_AM_BD, st_lbl_vi, st_val_am,
         'BAREVNÉ STRÁNKY', fmt(summary_data['total_color_all'])),
    ]
    card_w = PW / 4
    card_data = [[
        [Paragraph(lbl, lbl_st), Paragraph(val, val_st)]
        for bg, bd, lbl_st, val_st, lbl, val in card_configs
    ]]
    card_table = Table(card_data, colWidths=[card_w] * 4)
    card_styles = [
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 13),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 13),
        ('LEFTPADDING',   (0, 0), (-1, -1), 14),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
    ]
    for i, (bg, bd, _, _, _, _) in enumerate(card_configs):
        card_styles.append(('BACKGROUND', (i, 0), (i, 0), bg))
        card_styles.append(('BOX',        (i, 0), (i, 0), 0.75, bd))
        card_styles.append(('LINEABOVE',  (i, 0), (i, 0), 2.5,  bd))
    card_table.setStyle(TableStyle(card_styles))
    story.append(card_table)
    story.append(Spacer(1, 0.18 * inch))

    # ── 3. Section heading ────────────────────────────────────────────────
    story.append(Paragraph('Detaily zákazníků', st_sect))

    # ── 4. Per-customer blocks ────────────────────────────────────────────
    for customer in summary_data['customer_details']:

        # a) Customer name bar — indigo left strip + dark card
        # Strip time portion from date range (e.g. "01.01.2026 07:00:00 - ..." → "01.01.2026 - ...")
        date_display = re.sub(r'\s+\d{1,2}:\d{2}(:\d{2})?', '', customer['date_range']).strip()
        name_bar = Table(
            [['',
              Paragraph(customer['customer'], st_cname),
              Paragraph(date_display, st_date)]],
            colWidths=[0.06 * inch, PW * 0.60, PW * 0.34]
        )
        name_bar.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (0, -1),  INDIGO),
            ('BACKGROUND',    (1, 0), (-1, -1), CARD_RAISED),
            ('TOPPADDING',    (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING',   (0, 0), (0, -1),  0),
            ('RIGHTPADDING',  (0, 0), (0, -1),  0),
            ('LEFTPADDING',   (1, 0), (1, -1),  12),
            ('RIGHTPADDING',  (2, 0), (2, -1),  12),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        # b) Customer stats row — 4 mini counters
        cs_items = [
            ('TISKÁRNY',   fmt(customer['printers']),             st_cs_val),
            ('ČB STRÁNKY', fmt(customer['total_bw_billable']),    st_cs_val),
            ('BAREVNÉ',    fmt(customer['total_color_billable']), st_cs_val),
            ('CELKEM',     fmt(customer['total_billable']),       st_cs_val_am),
        ]
        cs_data = [[
            [Paragraph(lbl, st_cs_lbl), Paragraph(val, val_st)]
            for lbl, val, val_st in cs_items
        ]]
        cs_table = Table(cs_data, colWidths=[PW / 4] * 4)
        cs_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), CARD_BG),
            ('BACKGROUND',    (3, 0), (3, 0),   SC_AM_BG),
            ('BOX',           (3, 0), (3, 0),   0.75, SC_AM_BD),
            ('LINEBELOW',     (0, 0), (-1, -1), 0.5,  BORDER_LT),
            ('TOPPADDING',    (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ]))

        # c) Printer details table
        col_w = [1.90 * inch, 1.45 * inch, 1.10 * inch,
                 1.10 * inch, 1.62 * inch]

        printer_rows = [[
            Paragraph('MODEL',          st_th),
            Paragraph('SÉRIOVÉ ČÍSLO',  st_th),
            Paragraph('ČB',             st_th_r),
            Paragraph('BARVA',          st_th_r),
            Paragraph('CELKEM',         st_th_r),
        ]]

        for machine in customer['machines']:
            printer_rows.append([
                Paragraph(machine['model'],                    st_td),
                Paragraph(machine['serial'],                   st_mono),
                Paragraph(fmt(machine['bw_billable']),         st_td_r),
                Paragraph(fmt(machine['color_billable']),      st_td_r),
                Paragraph(fmt(machine['total_billable']),      st_td_b_r),
            ])

        printer_table = Table(printer_rows, colWidths=col_w)
        printer_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND',    (0, 0), (-1, 0),  CARD_BG),
            ('LINEBELOW',     (0, 0), (-1, 0),  0.75, BORDER_LT),
            # Data rows — subtle zebra
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [CARD_ALT, CARD_BG]),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.25, BORDER),
            # Padding
            ('TOPPADDING',    (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        block = KeepTogether([
            name_bar,
            cs_table,
            printer_table,
            Spacer(1, 0.2 * inch),
        ])
        story.append(block)

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buffer.seek(0)

    with open(filename, 'wb') as f:
        f.write(buffer.getvalue())

    return buffer
