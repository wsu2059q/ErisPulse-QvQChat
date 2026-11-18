"""本地预览 demo/index.html：python demo/serve_dev.py，然后开 http://127.0.0.1:8765/"""

import http.server
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
http.server.HTTPServer(("127.0.0.1", 8765), http.server.SimpleHTTPRequestHandler).serve_forever()
