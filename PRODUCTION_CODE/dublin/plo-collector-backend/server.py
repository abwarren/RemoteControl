#!/usr/bin/env python3
import json, os, re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import warnings

APP_DIR    = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR   = os.path.join(APP_DIR, "saved_hands")
PORT       = int(os.environ.get("PORT", "6001"))
INDEX_FILE = os.path.join(APP_DIR, "index.html")
os.makedirs(SAVE_DIR, exist_ok=True)
SEEN = set()

# Cache for list_hands
_HANDS_CACHE = None
_HANDS_CACHE_TIME = 0

def parse_hand(text):
    """Extract cards|board from either format."""
    # New rich format
    cards_m = re.search(r'cards\s*:\s*([^\n]+)', text)
    board_m = re.search(r'board\s*:\s*([^\n]+)', text)
    if cards_m:
        cards = cards_m.group(1).strip()
        board = board_m.group(1).strip() if board_m else ''
        if board in ('—', '-', ''):
            board = ''
        # normalise: remove spaces between cards
        def compact(s):
            return ''.join(s.split())
        return compact(cards) + '|' + compact(board)
    # Old format: already cards|board
    if '|' in text:
        return text.strip()
    return None

def list_hands(n=20):
    """List recent hands (optimized with caching)."""
    global _HANDS_CACHE, _HANDS_CACHE_TIME
    
    # Use cache if less than 2 seconds old
    now = datetime.utcnow().timestamp()
    if _HANDS_CACHE is not None and (now - _HANDS_CACHE_TIME) < 2:
        return _HANDS_CACHE[:n]
    
    files = sorted(
        [f for f in os.listdir(SAVE_DIR) if f.endswith('.txt')],
        reverse=True
    )[:n * 2]  # Read 2x needed, in case some fail
    
    out = []
    for f in files:
        if len(out) >= n:
            break
        path = os.path.join(SAVE_DIR, f)
        try:
            raw  = open(path, encoding='utf-8').read()
            mtime = os.path.getmtime(path)
            ts    = datetime.utcfromtimestamp(mtime).strftime('%H:%M:%S')
            parsed = parse_hand(raw)
            out.append({'file': f, 'text': parsed or raw.strip()[:80], 'time': ts})
        except Exception:
            pass
    
    # Cache result
    _HANDS_CACHE = out
    _HANDS_CACHE_TIME = now
    return out

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # silence access log

    def _cors(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.send_header("Content-Length","0")
        self.end_headers()

    def do_OPTIONS(self):
        self._cors()

    def _send(self, code=200, ct="text/html; charset=utf-8", body=b""):
        try:
            self.send_response(code)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(body)))
            self.send_header("Access-Control-Allow-Origin","*")
            self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers","Content-Type")
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            # Client closed connection - normal behavior, ignore
            pass
        except Exception as e:
            # Log but don't crash
            print(f"[ERROR] _send: {e}", flush=True)

    def do_GET(self):
        p = self.path.split('?')[0]
        if p in ('/', '/index.html', '/collector', '/collector/'):
            try:
                with open(INDEX_FILE, 'rb') as f:
                    self._send(200, 'text/html; charset=utf-8', f.read())
            except Exception:
                self._send(404, 'text/plain; charset=utf-8', b'Not found')
        elif p in ('/meta', '/collector/meta'):
            self._send(200, 'application/json', json.dumps({'save_dir': SAVE_DIR}).encode())
        elif p in ('/list', '/collector/list'):
            hands = list_hands(n=20)
            self._send(200, 'application/json', json.dumps({'hands': hands}).encode())
        else:
            self._send(404, 'text/plain; charset=utf-8', b'Not found')

    def do_POST(self):
        p = self.path.split('?')[0]
        if p not in ('/save', '/collector/save'):
            self._send(404, 'application/json', b'{"error":"Not found"}')
            return
        
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 1000000:  # 1MB limit
                self._send(413, 'application/json', b'{"error":"Payload too large"}')
                return
            
            raw    = self.rfile.read(length)
            payload = json.loads(raw.decode('utf-8'))
            text    = payload.get('text', '').strip()
            
            if not text:
                self._send(400, 'application/json', b'{"error":"Empty text"}')
                return
            
            ts       = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
            filename = f'hand_{ts}.txt'
            
            import hashlib
            h = hashlib.md5(text.encode()).hexdigest()
            if h in SEEN:
                self._send(200, 'application/json', json.dumps({'ok': True, 'dup': True}).encode())
                return
            
            SEEN.add(h)
            filepath = os.path.join(SAVE_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text + '\n')
            
            # Clear cache after saving
            global _HANDS_CACHE
            _HANDS_CACHE = None
            
            self._send(200, 'application/json', json.dumps({'ok': True, 'file': filename}).encode())
        except BrokenPipeError:
            pass
        except Exception as e:
            print(f"[ERROR] do_POST: {e}", flush=True)
            self._send(500, 'application/json', json.dumps({'error': str(e)}).encode())

if __name__ == '__main__':
    print(f'[hand-collector] Serving on 0.0.0.0:{PORT}', flush=True)
    HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
