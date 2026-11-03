import http.server
import socketserver
import os
import sys
import urllib.parse
import io
from PIL import Image

PORT = 8088
DASHBOARD_DIR = r"D:\OpenCode\Projects\Muramasa_HD\dashboard"
ORIG_DIR = r"D:\OpenCode\Projects\Muramasa_Art"
UPSCALED_DIR = r"D:\OpenCode\Projects\Muramasa_HD\upscaled_2k"
CACHE_DIR = os.path.join(DASHBOARD_DIR, "cache")

os.makedirs(os.path.join(CACHE_DIR, "orig"), exist_ok=True)
os.makedirs(os.path.join(CACHE_DIR, "2k"), exist_ok=True)

class CompressedHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        # Endpoint: compressed image comparison
        if parsed.path in ("/api/img/orig", "/api/img/2k"):
            params = urllib.parse.parse_qs(parsed.query)
            rel_path = params.get("path", [""])[0]
            if not rel_path:
                self.send_error(400, "Missing path query parameter")
                return

            kind = "orig" if parsed.path == "/api/img/orig" else "2k"
            self.serve_compressed(kind, rel_path)
            return

        super().do_GET()

    def serve_compressed(self, kind, rel_path):
        # Flatten path for cache filename
        safe_rel = rel_path.replace("/", "_").replace("\\", "_")
        cache_file = os.path.join(CACHE_DIR, kind, safe_rel + ".webp")

        if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
            try:
                with open(cache_file, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/webp")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                pass

        # Resolve source file
        if kind == "orig":
            src = os.path.join(ORIG_DIR, rel_path)
            quality = 85
        else:
            src = os.path.join(UPSCALED_DIR, rel_path)
            quality = 80

        if not os.path.exists(src):
            # Check fallback to thumbnail if full resolution not yet available
            thumb_name = os.path.basename(rel_path)
            thumb_src = os.path.join(DASHBOARD_DIR, "thumbs", thumb_name)
            if os.path.exists(thumb_src):
                src = thumb_src
            else:
                self.send_error(404, f"File not found: {rel_path}")
                return

        try:
            with Image.open(src) as im:
                buf = io.BytesIO()
                # High-efficiency WebP compression
                im.save(buf, format="WEBP", quality=quality, method=4)
                data = buf.getvalue()

            # Cache to disk for instant subsequent loads
            try:
                with open(cache_file, "wb") as f:
                    f.write(data)
            except Exception:
                pass

            self.send_response(200)
            self.send_header("Content-Type", "image/webp")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f"Error compressing image: {e}")

    def log_message(self, format, *args):
        pass # suppress request noise

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    os.chdir(DASHBOARD_DIR)
    socketserver.TCPServer.allow_reuse_address = True
    server = ThreadedHTTPServer(("", PORT), CompressedHandler)
    print(f"[Dashboard Server] Serving compressed WebP stream on http://localhost:{PORT}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
