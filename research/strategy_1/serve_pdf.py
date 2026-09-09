"""Serve only the finished research PDF for direct browser download.

No repository browsing, trading endpoints, or third-party dependencies.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from shutil import copyfileobj
from urllib.parse import urlsplit

PDF = Path(__file__).resolve().parents[2] / 'STRATEGY_1_ORB_FORENSIC_RESEARCH.pdf'
DOWNLOAD_NAME = 'Strategy-1-Opening-Range-Breakout.pdf'


class PDFHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_pdf(head_only=True)

    def do_GET(self):
        self.send_pdf()

    def send_pdf(self, head_only=False):
        path = urlsplit(self.path).path
        if path not in ('/', '/view', '/download', '/' + PDF.name, '/' + DOWNLOAD_NAME):
            self.send_error(404)
            return
        if not PDF.is_file():
            self.send_error(404, 'PDF not available')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/pdf')
        self.send_header('Content-Length', str(PDF.stat().st_size))
        disposition = 'inline' if path in ('/', '/view') else 'attachment'
        self.send_header('Content-Disposition', f'{disposition}; filename="{DOWNLOAD_NAME}"')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if not head_only:
            try:
                with PDF.open('rb') as stream:
                    copyfileobj(stream, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass


if __name__ == '__main__':
    server = ThreadingHTTPServer(('0.0.0.0', 8001), PDFHandler)
    print('Strategy 1 PDF download available on port 8001', flush=True)
    server.serve_forever()
