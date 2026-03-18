import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _register_utf8_fonts():
    """Register TrueType fonts that support Czech diacritics (UTF-8)."""
    _base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        # 1. Local fonts/ folder bundled with the app (DejaVu recommended, cross-platform)
        (
            os.path.join(_base, 'fonts', 'DejaVuSans.ttf'),
            os.path.join(_base, 'fonts', 'DejaVuSans-Bold.ttf'),
            os.path.join(_base, 'fonts', 'DejaVuSansMono.ttf'),
        ),
        # 2. Windows system — Arial
        (
            'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/arialbd.ttf',
            'C:/Windows/Fonts/cour.ttf',
        ),
        # 3. Windows system — Calibri fallback
        (
            'C:/Windows/Fonts/calibri.ttf',
            'C:/Windows/Fonts/calibrib.ttf',
            'C:/Windows/Fonts/cour.ttf',
        ),
        # 4. Linux — DejaVu (installed via fonts-dejavu or dejavu-fonts-ttf)
        (
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
        ),
        # 5. Linux — DejaVu (alternative path on some distros)
        (
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/dejavu/DejaVuSansMono.ttf',
        ),
        # 6. macOS — Arial (present on all macOS versions)
        (
            '/Library/Fonts/Arial.ttf',
            '/Library/Fonts/Arial Bold.ttf',
            '/Library/Fonts/Courier New.ttf',
        ),
        # 7. macOS — user fonts folder
        (
            os.path.expanduser('~/Library/Fonts/Arial.ttf'),
            os.path.expanduser('~/Library/Fonts/Arial Bold.ttf'),
            os.path.expanduser('~/Library/Fonts/Courier New.ttf'),
        ),
    ]
    for reg, bold, mono in candidates:
        if os.path.exists(reg) and os.path.exists(bold) and os.path.exists(mono):
            try:
                pdfmetrics.registerFont(TTFont('AppFont',      reg))
                pdfmetrics.registerFont(TTFont('AppFont-Bold', bold))
                pdfmetrics.registerFont(TTFont('AppFont-Mono', mono))
                print(f"[OK] PDF fonts registered: {os.path.basename(reg)}")
                return True
            except Exception as exc:
                print(f"[WARN] Font registration failed ({reg}): {exc}")
    print("[WARN] No UTF-8 fonts found - PDF will use Helvetica (Czech diacritics may be missing)")
    return False


_PDF_FONTS_OK = _register_utf8_fonts()
_FONT_REG  = 'AppFont'      if _PDF_FONTS_OK else 'Helvetica'
_FONT_BOLD = 'AppFont-Bold' if _PDF_FONTS_OK else 'Helvetica-Bold'
_FONT_MONO = 'AppFont-Mono' if _PDF_FONTS_OK else 'Courier'
