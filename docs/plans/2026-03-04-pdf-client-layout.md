# PDF Client Layout Improvement Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the generated PDF report for client readability by removing internal contract columns, adding a per-printer total column, increasing font sizes and padding, and highlighting the customer total with amber accent.

**Architecture:** All changes are isolated to `reports.py` → `generate_pdf_report()`. No route, frontend, or data-model changes needed. The function already receives all data it needs; we just change what we render and how.

**Tech Stack:** Python, ReportLab (`reportlab.platypus`, `reportlab.lib`)

---

### Task 1: Remove internal columns, add CELKEM column to printer table

**Files:**
- Modify: `reports.py` (printer_rows header + data loop, ~lines 379–422)

**Step 1: Update column widths**

Replace the 6-column `col_w` with a 5-column layout. In `generate_pdf_report()` find:
```python
col_w = [2.05 * inch, 1.35 * inch, 0.9 * inch,
         0.9 * inch,  0.85 * inch, 1.32 * inch]
```
Replace with:
```python
col_w = [2.10 * inch, 1.45 * inch, 1.10 * inch,
         1.10 * inch, 1.62 * inch]
```

**Step 2: Update table header row**

Find the `printer_rows` list initialisation:
```python
printer_rows = [[
    Paragraph('MODEL',          st_th),
    Paragraph('SÉRIOVÉ ČÍSLO',  st_th),
    Paragraph('ČB',             st_th_r),
    Paragraph('BARVA',          st_th_r),
    Paragraph('ZBÝVÁ',          st_th_r),
    Paragraph('NÁKLADY/MĚS.',   st_th_r),
]]
```
Replace with:
```python
printer_rows = [[
    Paragraph('MODEL',          st_th),
    Paragraph('SÉRIOVÉ ČÍSLO',  st_th),
    Paragraph('ČB',             st_th_r),
    Paragraph('BARVA',          st_th_r),
    Paragraph('CELKEM',         st_th_r),
]]
```

**Step 3: Update data row loop**

Find the block inside `for machine in customer['machines']:` that builds `months_para`, `cost_para`, and appends to `printer_rows`. Replace the entire inner block:

```python
# BEFORE (remove this):
        contract = machine.get('contract_info', {})
        months_remaining = contract.get('months_remaining')

        if not contract.get('has_contract') or months_remaining is None:
            months_para = Paragraph(...)
        elif months_remaining == 0:
            months_para = Paragraph(...)
        elif months_remaining <= 3:
            months_para = Paragraph(...)
        elif months_remaining <= 6:
            months_para = Paragraph(...)
        else:
            months_para = Paragraph(...)

        monthly_cost = contract.get('monthly_cost', 0)
        cost_para = Paragraph(...)

        printer_rows.append([
            Paragraph(machine['model'],  st_td),
            Paragraph(machine['serial'], st_mono),
            Paragraph(fmt(machine['bw_billable']),    st_td_r),
            Paragraph(fmt(machine['color_billable']), st_td_r),
            months_para,
            cost_para,
        ])
```

```python
# AFTER (replace with):
        total_billable = machine['bw_billable'] + machine['color_billable']
        printer_rows.append([
            Paragraph(machine['model'],               st_td),
            Paragraph(machine['serial'],              st_mono),
            Paragraph(fmt(machine['bw_billable']),    st_td_r),
            Paragraph(fmt(machine['color_billable']), st_td_r),
            Paragraph(fmt(total_billable),            st_td_b_r),
        ])
```

**Step 4: Verify the app still starts and a report generates without error**

```bash
python app.py
```
Upload a CSV, generate a report, open the PDF. Confirm 5 columns visible: MODEL, SÉRIOVÉ ČÍSLO, ČB, BARVA, CELKEM. Confirm no ZBÝVÁ / NÁKLADY/MĚS. columns.

---

### Task 2: Increase font sizes and cell padding

**Files:**
- Modify: `reports.py` (paragraph styles + table style, ~lines 255–266 and 425–438)

**Step 1: Increase table text styles**

Find:
```python
st_th     = ParagraphStyle('TH',   fontName=_FONT_BOLD, fontSize=7,
                           textColor=TEXT_MD)
st_th_r   = ParagraphStyle('THR',  fontName=_FONT_BOLD, fontSize=7,
                           textColor=TEXT_MD, alignment=TA_RIGHT)
st_td     = ParagraphStyle('TD',   fontName=_FONT_REG,  fontSize=8,
                           textColor=TEXT_HI)
st_td_r   = ParagraphStyle('TDR',  fontName=_FONT_REG,  fontSize=8,
                           textColor=TEXT_HI, alignment=TA_RIGHT)
st_td_b_r = ParagraphStyle('TDBR', fontName=_FONT_BOLD, fontSize=8,
                           textColor=TEXT_HI, alignment=TA_RIGHT)
st_mono   = ParagraphStyle('MN',   fontName=_FONT_MONO, fontSize=7,
                           textColor=TEXT_MD)
```
Replace with:
```python
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
```

**Step 2: Increase cell padding in printer_table style**

Find in the `printer_table.setStyle(...)` block:
```python
('TOPPADDING',    (0, 0), (-1, -1), 8),
('BOTTOMPADDING', (0, 0), (-1, -1), 8),
('LEFTPADDING',   (0, 0), (-1, -1), 10),
('RIGHTPADDING',  (0, 0), (-1, -1), 10),
```
Replace with:
```python
('TOPPADDING',    (0, 0), (-1, -1), 11),
('BOTTOMPADDING', (0, 0), (-1, -1), 11),
('LEFTPADDING',   (0, 0), (-1, -1), 10),
('RIGHTPADDING',  (0, 0), (-1, -1), 10),
```

**Step 3: Verify**

Generate a report. Confirm table text is noticeably larger, rows have more breathing room.

---

### Task 3: Highlight CELKEM counter with amber accent in customer summary block

**Files:**
- Modify: `reports.py` (cs_table construction, ~lines 355–373)

**Step 1: Update customer stat labels and values**

Find:
```python
st_cs_lbl = ParagraphStyle('CSL',  fontName=_FONT_BOLD, fontSize=7,
                           textColor=TEXT_MD, spaceAfter=3)
st_cs_val = ParagraphStyle('CSV',  fontName=_FONT_BOLD, fontSize=12,
                           textColor=TEXT_HI)
```
Replace with:
```python
st_cs_lbl     = ParagraphStyle('CSL',  fontName=_FONT_BOLD, fontSize=7,
                               textColor=TEXT_MD, spaceAfter=3)
st_cs_val     = ParagraphStyle('CSV',  fontName=_FONT_BOLD, fontSize=15,
                               textColor=TEXT_HI)
st_cs_val_am  = ParagraphStyle('CSVA', fontName=_FONT_BOLD, fontSize=15,
                               textColor=VAL_AM)
```

**Step 2: Use amber style for the CELKEM cell**

Find the `cs_items` block:
```python
cs_items = [
    ('TISKÁRNY',   str(customer['printers'])),
    ('ČB STRÁNKY', fmt(customer['total_bw_billable'])),
    ('BAREVNÉ',    fmt(customer['total_color_billable'])),
    ('CELKEM',     fmt(customer['total_billable'])),
]
cs_data = [[
    [Paragraph(lbl, st_cs_lbl), Paragraph(val, st_cs_val)]
    for lbl, val in cs_items
]]
```
Replace with:
```python
cs_items = [
    ('TISKÁRNY',   fmt(customer['printers']),              st_cs_val),
    ('ČB STRÁNKY', fmt(customer['total_bw_billable']),     st_cs_val),
    ('BAREVNÉ',    fmt(customer['total_color_billable']),  st_cs_val),
    ('CELKEM',     fmt(customer['total_billable']),        st_cs_val_am),
]
cs_data = [[
    [Paragraph(lbl, st_cs_lbl), Paragraph(val, val_st)]
    for lbl, val, val_st in cs_items
]]
```

**Step 3: Apply amber background to the CELKEM (4th) cell**

Find `cs_table.setStyle(TableStyle([`:
```python
cs_table.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, -1), CARD_BG),
    ('LINEBELOW',     (0, 0), (-1, -1), 0.5,  BORDER_LT),
    ('TOPPADDING',    (0, 0), (-1, -1), 9),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ('LEFTPADDING',   (0, 0), (-1, -1), 12),
    ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
]))
```
Replace with:
```python
cs_table.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, -1), CARD_BG),
    ('BACKGROUND',    (3, 0), (3, 0),   SC_AM_BG),
    ('BOX',           (3, 0), (3, 0),   0.75, SC_AM_BD),
    ('LINEBELOW',     (0, 0), (-1, -1), 0.5,  BORDER_LT),
    ('TOPPADDING',    (0, 0), (-1, -1), 9),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ('LEFTPADDING',   (0, 0), (-1, -1), 12),
    ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
]))
```

**Step 4: Final verification**

Generate a report with at least one customer. Confirm:
- Customer summary row: CELKEM number is amber-coloured on an amber-tinted background
- CELKEM number is visibly larger than before (15pt)
- Printer table: 5 columns, no internal contract data, CELKEM column shows correct sum of ČB + BARVA per row

---
