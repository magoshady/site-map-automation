#!/usr/bin/env python3
"""
PV Site Plan PDF Overlay Stamper
=================================
Takes an EXISTING PV site plan PDF (with satellite image already embedded)
and stamps fixed + variable overlays onto it:

  FIXED (same every time):
    - Legend (left side)
    - North arrow (top-right of image area)
    - Warning banner (bottom)

  VARIABLE (per site):
    - Address, system size, max DC voltage, install date

Usage (CLI args):
    python3 stamp_pv_site_plan.py \
        --input /path/to/original_site_plan.pdf \
        --address "1 Yeramba Avenue, Caringbah South NSW 2229" \
        --system-size "7.99" \
        --max-dc-voltage "600" \
        --install-date "11th March 2026" \
        --output /path/to/stamped_output.pdf

Usage (JSON config):
    python3 stamp_pv_site_plan.py --config /path/to/config.json

JSON config format:
{
    "input_pdf": "/path/to/original_site_plan.pdf",
    "address": "1 Yeramba Avenue, Caringbah South NSW 2229",
    "system_size_kwdc": "7.99",
    "max_dc_voltage": "600",
    "install_date": "11th March 2026",
    "output_pdf": "/path/to/stamped_output.pdf",
    "company_name": "SGI Energy",
    "page_index": 0
}

Designed to be called from n8n via Execute Command node.
"""

import argparse
import io
import json
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import (
    HexColor, white, black, red, yellow, grey, Color
)
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter


# ── Layout constants ───────────────────────────────────────────────────────────

# Default asset paths (override via env var PV_ASSETS_DIR)
ASSETS_DIR = os.environ.get(
    "PV_ASSETS_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
)

BRAND_PRIMARY = HexColor("#D32F2F")
BRAND_DARK = HexColor("#333333")
BRAND_GREY = HexColor("#666666")


# ── Overlay drawing functions ──────────────────────────────────────────────────

def draw_legend_vector(c, x, y):
    """Draw the component legend as vector graphics matching the branded icons."""
    items = [
        ("You are here",           "red_dot"),
        ("Rooftop DC isolator",    "dc_isolator"),
        ("Inverter",               "inverter"),
        ("Meter box",              "meter_box"),
        ("Disconnection point",    "disconnect"),
        ("DC cable path internal", "cable_red"),
        ("DC cable path external", "cable_blue"),
        ("Sub board",              "sub_board"),
        ("Battery",                "battery"),
    ]

    legend_w = 44 * mm
    item_h = 7.5 * mm
    padding = 4 * mm
    legend_h = len(items) * item_h + padding * 2

    # Extended white background to cover full satellite image height
    # The bg extends beyond the legend content area by extend_up/extend_down
    from reportlab.lib.units import mm as _mm
    extend_down = 10 * _mm
    extend_up = 5 * _mm
    bg_y = y - extend_down
    bg_h = legend_h + extend_down + extend_up

    c.saveState()
    c.setFillColor(white)
    c.rect(x, bg_y, legend_w, bg_h, fill=1, stroke=0)
    c.restoreState()

    cur_y = y + legend_h - padding - item_h + 1.5 * mm
    icon_w = 8 * mm
    icon_h = 5 * mm

    for label, icon_type in items:
        icon_x = x + padding
        icon_cx = icon_x + icon_w / 2
        icon_cy = cur_y + icon_h / 2 - 0.5 * mm
        text_x = x + padding + icon_w + 3 * mm

        c.saveState()

        if icon_type == "red_dot":
            c.setFillColor(red)
            c.ellipse(icon_x + 1 * mm, icon_cy - 1.8 * mm,
                      icon_x + icon_w - 1 * mm, icon_cy + 1.8 * mm,
                      fill=1, stroke=0)

        elif icon_type == "dc_isolator":
            c.setStrokeColor(black)
            c.setLineWidth(1.2)
            c.rect(icon_x, cur_y - 0.5 * mm, icon_w, icon_h, fill=0, stroke=1)
            c.setLineWidth(0.8)
            path = c.beginPath()
            path.moveTo(icon_x + 1 * mm, icon_cy + 1 * mm)
            path.lineTo(icon_x + 2.5 * mm, icon_cy - 1 * mm)
            path.lineTo(icon_x + 4 * mm, icon_cy + 1 * mm)
            path.lineTo(icon_x + 5.5 * mm, icon_cy - 1 * mm)
            c.drawPath(path, fill=0, stroke=1)
            c.line(icon_x + 5.5 * mm, icon_cy - 1 * mm,
                   icon_x + icon_w - 1 * mm, icon_cy - 1 * mm)
            c.setFillColor(black)
            path2 = c.beginPath()
            path2.moveTo(icon_x + icon_w - 1 * mm, icon_cy - 1 * mm)
            path2.lineTo(icon_x + icon_w - 2.2 * mm, icon_cy - 0.3 * mm)
            path2.lineTo(icon_x + icon_w - 2.2 * mm, icon_cy - 1.7 * mm)
            path2.close()
            c.drawPath(path2, fill=1, stroke=0)

        elif icon_type == "inverter":
            c.setStrokeColor(black)
            c.setLineWidth(1.2)
            c.rect(icon_x, cur_y - 0.5 * mm, icon_w, icon_h, fill=0, stroke=1)
            c.setLineWidth(0.8)
            for offset in [1.2 * mm, 0, -1.2 * mm]:
                path = c.beginPath()
                ly = icon_cy + offset
                path.moveTo(icon_x + 1.5 * mm, ly)
                path.curveTo(icon_x + 3 * mm, ly + 0.8 * mm,
                             icon_x + 5 * mm, ly - 0.8 * mm,
                             icon_x + icon_w - 1.5 * mm, ly)
                c.drawPath(path, fill=0, stroke=1)

        elif icon_type == "meter_box":
            c.setStrokeColor(black)
            c.setLineWidth(1.5)
            radius = 2.5 * mm
            c.circle(icon_cx, icon_cy, radius, fill=0, stroke=1)
            c.setFillColor(black)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(icon_cx, icon_cy - 1.2 * mm, "M")

        elif icon_type == "disconnect":
            c.setStrokeColor(HexColor("#22AA22"))
            c.setLineWidth(1.8)
            radius = 2.5 * mm
            c.circle(icon_cx, icon_cy, radius, fill=0, stroke=1)
            c.setFillColor(red)
            c.setFont("Helvetica-Bold", 6)
            c.drawCentredString(icon_cx, icon_cy - 1 * mm, "DP")

        elif icon_type == "cable_red":
            c.setStrokeColor(red)
            c.setLineWidth(2)
            path = c.beginPath()
            path.moveTo(icon_x, icon_cy)
            path.curveTo(icon_x + 1.5 * mm, icon_cy + 2.5 * mm,
                         icon_x + 3 * mm, icon_cy + 2.5 * mm,
                         icon_x + 4 * mm, icon_cy)
            path.curveTo(icon_x + 5 * mm, icon_cy - 2.5 * mm,
                         icon_x + 6.5 * mm, icon_cy - 2.5 * mm,
                         icon_x + icon_w, icon_cy)
            c.drawPath(path, fill=0, stroke=1)

        elif icon_type == "cable_blue":
            c.setStrokeColor(HexColor("#2244CC"))
            c.setLineWidth(2)
            path = c.beginPath()
            path.moveTo(icon_x, icon_cy)
            path.curveTo(icon_x + 1.5 * mm, icon_cy + 2.5 * mm,
                         icon_x + 3 * mm, icon_cy + 2.5 * mm,
                         icon_x + 4 * mm, icon_cy)
            path.curveTo(icon_x + 5 * mm, icon_cy - 2.5 * mm,
                         icon_x + 6.5 * mm, icon_cy - 2.5 * mm,
                         icon_x + icon_w, icon_cy)
            c.drawPath(path, fill=0, stroke=1)

        elif icon_type == "sub_board":
            c.setStrokeColor(black)
            c.setLineWidth(1.2)
            c.rect(icon_x, cur_y - 0.5 * mm, icon_w, icon_h, fill=0, stroke=1)
            c.setLineWidth(0.6)
            for i in range(0, 10):
                lx = icon_x + i * 1.2 * mm
                c.line(lx, cur_y - 0.5 * mm,
                       lx + icon_h * 0.7, cur_y - 0.5 * mm + icon_h)

        elif icon_type == "battery":
            c.setStrokeColor(black)
            c.setLineWidth(1.2)
            gap = 1.8 * mm
            for i, bx in enumerate([icon_x + 1 * mm, icon_x + 1 * mm + gap,
                                     icon_x + 1 * mm + gap * 2, icon_x + 1 * mm + gap * 3]):
                h = icon_h * 0.8 if (i % 2 == 0) else icon_h * 0.5
                by = icon_cy - h / 2
                c.line(bx, by, bx, by + h)

        c.restoreState()

        c.setFillColor(BRAND_DARK)
        c.setFont("Helvetica", 7)
        c.drawString(text_x, cur_y + 1 * mm, label)
        cur_y -= item_h


def draw_legend_image(c, image_path, x, y, target_w=42 * mm, page_h=None):
    """Paste the legend PNG image with white background covering satellite image area."""
    if not os.path.exists(image_path):
        print(f"  WARNING: Legend image not found: {image_path}", file=sys.stderr)
        draw_legend_vector(c, x, y)
        return
    img = ImageReader(image_path)
    iw, ih = img.getSize()
    scale = target_w / iw
    target_h = ih * scale

    # White background covering full satellite image height
    if page_h:
        # Top: just below address bar (page_h - 43mm)
        bg_top = page_h - 43 * mm
        # Bottom: just above details block (margin + warning + gap + details = ~59mm)
        bg_bottom = 59 * mm
        bg_y = bg_bottom
        bg_h = bg_top - bg_bottom
    else:
        bg_y = y - 10 * mm
        bg_h = target_h + 20 * mm

    c.saveState()
    c.setFillColor(white)
    c.rect(x, bg_y, target_w, bg_h, fill=1, stroke=0)
    c.restoreState()

    c.drawImage(img, x, y, width=target_w, height=target_h,
                preserveAspectRatio=True, mask='auto')


def draw_north_arrow_vector(c, cx, cy, size=12 * mm):
    """Draw a north arrow at the given centre point."""
    c.saveState()

    # White background circle
    c.setFillColor(white)
    c.setStrokeColor(black)
    c.setLineWidth(1)
    c.circle(cx, cy, size * 0.55, fill=1, stroke=1)

    # Arrow (filled black)
    c.setFillColor(black)
    path = c.beginPath()
    path.moveTo(cx, cy + size * 0.4)
    path.lineTo(cx - size * 0.15, cy - size * 0.15)
    path.lineTo(cx, cy - size * 0.05)
    path.lineTo(cx + size * 0.15, cy - size * 0.15)
    path.close()
    c.drawPath(path, fill=1, stroke=0)

    # "N" label
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(cx, cy - size * 0.42, "N")

    c.restoreState()


def draw_north_arrow_image(c, image_path, x, y, target_h=20 * mm):
    """Paste the north arrow PNG image."""
    if not os.path.exists(image_path):
        print(f"  WARNING: North arrow image not found: {image_path}", file=sys.stderr)
        draw_north_arrow_vector(c, x + 8 * mm, y + 10 * mm)
        return
    img = ImageReader(image_path)
    iw, ih = img.getSize()
    scale = target_h / ih
    target_w = iw * scale
    c.drawImage(img, x, y, width=target_w, height=target_h,
                preserveAspectRatio=True, mask='auto')


def draw_warning_vector(c, x, y, w):
    """Draw the yellow warning banner."""
    h = 14 * mm

    c.saveState()

    # Yellow background
    c.setFillColor(yellow)
    c.rect(x, y, w, h, fill=1, stroke=0)

    # Red top border
    c.setStrokeColor(BRAND_PRIMARY)
    c.setLineWidth(2)
    c.line(x, y + h, x + w, y + h)

    # Warning triangle
    tri_size = 10 * mm
    tri_x = x + 5 * mm
    tri_cy = y + h / 2

    c.setFillColor(yellow)
    c.setStrokeColor(black)
    c.setLineWidth(2)

    path = c.beginPath()
    path.moveTo(tri_x + tri_size / 2, tri_cy + tri_size * 0.4)
    path.lineTo(tri_x, tri_cy - tri_size * 0.35)
    path.lineTo(tri_x + tri_size, tri_cy - tri_size * 0.35)
    path.close()
    c.drawPath(path, fill=1, stroke=1)

    # Lightning bolt
    c.setLineWidth(1.8)
    bolt_x = tri_x + tri_size / 2
    bolt_y = tri_cy
    path2 = c.beginPath()
    path2.moveTo(bolt_x + 0.5 * mm, bolt_y + 3 * mm)
    path2.lineTo(bolt_x - 1 * mm, bolt_y + 0.3 * mm)
    path2.lineTo(bolt_x + 0.5 * mm, bolt_y + 0.3 * mm)
    path2.lineTo(bolt_x - 0.5 * mm, bolt_y - 3 * mm)
    c.drawPath(path2, fill=0, stroke=1)

    # Text
    text_x = tri_x + tri_size + 5 * mm
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(text_x, y + h - 5.5 * mm, "WARNING")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(text_x, y + 5 * mm,
                 "DC Disconnection Points can only be operated")
    c.drawString(text_x, y + 1.5 * mm,
                 "by suitably qualified personnel.")

    c.restoreState()


def draw_warning_image(c, image_path, x, y, target_w=None):
    """Paste the warning PNG image."""
    if not os.path.exists(image_path):
        print(f"  WARNING: Warning image not found: {image_path}", file=sys.stderr)
        draw_warning_vector(c, x, y, target_w or 170 * mm)
        return
    img = ImageReader(image_path)
    iw, ih = img.getSize()
    if target_w:
        scale = target_w / iw
    else:
        scale = 1
    target_h = ih * scale
    c.drawImage(img, x, y, width=target_w or iw, height=target_h,
                preserveAspectRatio=True, mask='auto')


def draw_details_block(c, x, y, w, address, system_size, max_dc_voltage, install_date):
    """Draw the variable address/details text block."""
    block_h = 24 * mm

    c.saveState()
    c.setFillColor(white)
    c.roundRect(x, y, w, block_h, 2, fill=1, stroke=0)

    text_x = x + 4 * mm
    line_h = 5.5 * mm
    cur_y = y + block_h - 6 * mm

    c.setFillColor(BRAND_DARK)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(text_x, cur_y, f"ADDRESS:  {address}")
    cur_y -= line_h

    c.drawString(text_x, cur_y, f"PV ARRAY SIZE (kWDC):  {system_size}kWDC")
    cur_y -= line_h

    voltage_str = f"{max_dc_voltage} VDC" if max_dc_voltage else "VDC"
    c.drawString(text_x, cur_y, f"MAX DC VOLTAGE (V):       {voltage_str}")
    cur_y -= line_h

    # Superscript "th" / "st" / "nd" / "rd" handling
    c.drawString(text_x, cur_y, f"INSTALL DATE:   {install_date}")

    c.restoreState()


def draw_footer(c, page_w, company_name):
    """Draw a simple footer line."""
    c.saveState()
    footer_y = 8 * mm
    c.setStrokeColor(grey)
    c.setLineWidth(0.5)
    c.line(15 * mm, footer_y, page_w - 15 * mm, footer_y)

    c.setFillColor(BRAND_GREY)
    c.setFont("Helvetica", 7)
    c.drawString(15 * mm, footer_y - 4 * mm, company_name)
    c.restoreState()


# ── Main stamping function ─────────────────────────────────────────────────────

def stamp_pv_site_plan(
    input_pdf: str,
    address: str,
    system_size_kwdc: str,
    max_dc_voltage: str,
    install_date: str,
    output_pdf: str,
    company_name: str = "SGI Energy",
    page_index: int = 0,
    use_png_overlays: bool = False,
    legend_image: str = None,
    north_arrow_image: str = None,
    warning_image: str = None,
):
    """
    Stamp overlays onto an existing PV site plan PDF.

    Args:
        input_pdf: Path to the original PDF (with satellite image)
        address: Site address
        system_size_kwdc: e.g. "7.99"
        max_dc_voltage: e.g. "600" or ""
        install_date: e.g. "11th March 2026"
        output_pdf: Where to save the stamped PDF
        company_name: For footer
        page_index: Which page to stamp (0-based), default first page
        use_png_overlays: If True, use PNG images; if False, draw vectors
        legend_image: Path to legend PNG (when use_png_overlays=True)
        north_arrow_image: Path to north arrow PNG
        warning_image: Path to warning PNG
    """
    # Read the original PDF
    reader = PdfReader(input_pdf)
    if page_index >= len(reader.pages):
        print(f"ERROR: PDF has {len(reader.pages)} pages, "
              f"requested page_index={page_index}", file=sys.stderr)
        sys.exit(1)

    page = reader.pages[page_index]
    page_w = float(page.mediabox.width)
    page_h = float(page.mediabox.height)

    print(f"Input PDF page size: {page_w:.1f} x {page_h:.1f} points "
          f"({page_w/72:.1f}\" x {page_h/72:.1f}\")")

    # ── Create overlay PDF in memory ──
    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(page_w, page_h))

    margin = 15 * mm
    content_w = page_w - 2 * margin

    # ── Legend (left side, vertically centred in image area) ──
    legend_x = margin + 3 * mm
    legend_y = page_h * 0.46  # Moved up from 0.42

    # Prefer PNG legend: explicit path > default asset > vector fallback
    legend_path = legend_image or os.path.join(ASSETS_DIR, "legend.png")
    if os.path.exists(legend_path):
        draw_legend_image(c, legend_path, legend_x, legend_y, page_h=page_h)
    else:
        draw_legend_vector(c, legend_x, legend_y)

    # ── North arrow (top-right area) ──
    if use_png_overlays and north_arrow_image:
        draw_north_arrow_image(
            c, north_arrow_image,
            page_w - margin - 20 * mm,
            page_h - margin - 35 * mm  # Below any header
        )
    else:
        draw_north_arrow_vector(
            c,
            page_w - margin - 12 * mm,
            page_h - margin - 45 * mm  # Brought down ~20mm from previous -25mm
        )

    # ── Details block (bottom area, above warning) ──
    details_y = margin + 20 * mm  # Above warning
    draw_details_block(
        c, margin, details_y, content_w,
        address, system_size_kwdc, max_dc_voltage, install_date
    )

    # ── Warning banner (very bottom) ──
    warning_y = margin + 2 * mm

    if use_png_overlays and warning_image:
        draw_warning_image(c, warning_image, margin, warning_y, target_w=content_w)
    else:
        draw_warning_vector(c, margin, warning_y, content_w)

    # ── Footer ──
    draw_footer(c, page_w, company_name)

    c.save()

    # ── Merge overlay onto original page ──
    overlay_buffer.seek(0)
    overlay_reader = PdfReader(overlay_buffer)
    overlay_page = overlay_reader.pages[0]

    page.merge_page(overlay_page)

    # ── Write output (only the stamped page, drop any extra pages) ──
    writer = PdfWriter()
    writer.add_page(page)

    total_pages = len(reader.pages)
    if total_pages > 1:
        print(f"  Dropped {total_pages - 1} extra page(s), outputting stamped page only")

    with open(output_pdf, "wb") as f:
        writer.write(f)

    print(f"Stamped PDF saved: {output_pdf}")
    return output_pdf


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Stamp overlays onto an existing PV Site Plan PDF"
    )
    parser.add_argument("--config", help="Path to JSON config file")
    parser.add_argument("--input", help="Path to input PDF")
    parser.add_argument("--address", help="Site address")
    parser.add_argument("--system-size", help="System size in kWDC")
    parser.add_argument("--max-dc-voltage", default="", help="Max DC voltage")
    parser.add_argument("--install-date", default="", help="Install date")
    parser.add_argument("--output", default="stamped_site_plan.pdf",
                        help="Output PDF path")
    parser.add_argument("--company-name", default="SGI Energy")
    parser.add_argument("--page-index", type=int, default=0,
                        help="Which page to stamp (0-based)")
    parser.add_argument("--use-png-overlays", action="store_true",
                        help="Use PNG images instead of vector overlays")
    parser.add_argument("--legend-image", default=None)
    parser.add_argument("--north-arrow-image", default=None)
    parser.add_argument("--warning-image", default=None)

    args = parser.parse_args()

    if args.config:
        with open(args.config) as f:
            cfg = json.load(f)
        stamp_pv_site_plan(
            input_pdf=cfg["input_pdf"],
            address=cfg.get("address", ""),
            system_size_kwdc=cfg.get("system_size_kwdc", ""),
            max_dc_voltage=cfg.get("max_dc_voltage", ""),
            install_date=cfg.get("install_date", ""),
            output_pdf=cfg.get("output_pdf", "stamped_site_plan.pdf"),
            company_name=cfg.get("company_name", "SGI Energy"),
            page_index=cfg.get("page_index", 0),
            use_png_overlays=cfg.get("use_png_overlays", False),
            legend_image=cfg.get("legend_image"),
            north_arrow_image=cfg.get("north_arrow_image"),
            warning_image=cfg.get("warning_image"),
        )
    else:
        if not args.input:
            parser.error("--input is required (or use --config)")
        if not args.address:
            parser.error("--address is required (or use --config)")

        stamp_pv_site_plan(
            input_pdf=args.input,
            address=args.address,
            system_size_kwdc=args.system_size or "",
            max_dc_voltage=args.max_dc_voltage,
            install_date=args.install_date,
            output_pdf=args.output,
            company_name=args.company_name,
            page_index=args.page_index,
            use_png_overlays=args.use_png_overlays,
            legend_image=args.legend_image,
            north_arrow_image=args.north_arrow_image,
            warning_image=args.warning_image,
        )


if __name__ == "__main__":
    main()
