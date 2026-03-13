"""
Vercel serverless function: PV Site Plan PDF Stamper

POST /api/stamp
  Body (JSON):
    - pdf_url:           Signed URL to download the input PDF
    - address:           Site address
    - system_size_kwdc:  e.g. "7.99"
    - max_dc_voltage:    e.g. "600"
    - install_date:      e.g. "11th March 2026"
    - company_name:      (optional, default "SGI Energy")
    - page_index:        (optional, default 0)

  Returns: stamped PDF binary (application/pdf)

GET /api/stamp
  Returns: health check JSON
"""

import base64
import json
import os
import sys
import tempfile
import urllib.request
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stamp_pv_site_plan import stamp_pv_site_plan

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGEND_PATH = os.path.join(PROJECT_ROOT, "legend.png")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))

            pdf_url = body.get("pdf_url")
            pdf_base64 = body.get("pdf_base64")

            if not pdf_url and not pdf_base64:
                self._error(400, "Provide either pdf_url or pdf_base64")
                return

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                input_path = f.name
                if pdf_url:
                    req = urllib.request.Request(pdf_url, headers={
                        "User-Agent": "Mozilla/5.0 (compatible; PVStamper/1.0)",
                        "Accept": "*/*",
                    })
                    with urllib.request.urlopen(req) as resp:
                        f.write(resp.read())
                else:
                    f.write(base64.b64decode(pdf_base64))

            output_path = input_path.replace(".pdf", "_stamped.pdf")

            stamp_pv_site_plan(
                input_pdf=input_path,
                address=body.get("address", ""),
                system_size_kwdc=str(body.get("system_size_kwdc", "")),
                max_dc_voltage=str(body.get("max_dc_voltage", "")),
                install_date=body.get("install_date", ""),
                output_pdf=output_path,
                company_name=body.get("company_name", "SGI Energy"),
                page_index=body.get("page_index", 0),
                legend_image=LEGEND_PATH,
            )

            with open(output_path, "rb") as f:
                stamped_bytes = f.read()

            os.unlink(input_path)
            os.unlink(output_path)

            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(stamped_bytes)))
            self.end_headers()
            self.wfile.write(stamped_bytes)

        except Exception as e:
            self._error(500, str(e))

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "service": "PV Site Plan Stamper"}).encode())

    def _error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
