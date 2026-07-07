"""Simple demo server for testing migration-api-checker."""

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

HOST = "localhost"
PORT_BEFORE = 8000
PORT_AFTER = 8001


class BeforeHandler(BaseHTTPRequestHandler):
    """Mock API handler - BEFORE migration."""

    def _set_headers(self, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def _json_response(self, data: dict, status: int = 200):
        self._set_headers(status)
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if self.path.startswith("/v1/users"):
            # Support query params like ?page=1&size=10
            self._json_response({
                "data": [
                    {"id": 1, "name": "Alice", "email": "alice@example.com", "createdAt": "2024-01-01", "updatedAt": time.strftime("%Y-%m-%d")},
                    {"id": 2, "name": "Bob", "email": "bob@example.com", "createdAt": "2024-01-02", "updatedAt": time.strftime("%Y-%m-%d")},
                ],
                "total": 2,
                "timestamp": time.time(),
            })
        elif self.path == "/v1/orders/123":
            self._json_response({
                "id": "123",
                "status": "delivered",
                "amount": 99.99,
                "processedAt": time.time(),
            })
        elif self.path == "/v1/products":
            self._json_response({
                "items": [
                    {"sku": "P001", "name": "Laptop", "price": 1000},
                    {"sku": "P002", "name": "Mouse", "price": 25},
                ],
                "count": 2,
            })
        elif self.path == "/v1/status":
            self._json_response({"status": "ok", "code": 200})
        else:
            self._json_response({"error": "Not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if self.path == "/v1/users":
            data = json.loads(body) if body else {}
            self._json_response({
                "id": 100,
                "name": data.get("name", "New User"),
                "email": data.get("email", "new@example.com"),
                "createdAt": time.strftime("%Y-%m-%d"),
                "updatedAt": time.strftime("%Y-%m-%d"),
            }, status=201)
        else:
            self._json_response({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        """Suppress logging."""
        pass


class AfterHandler(BaseHTTPRequestHandler):
    """Mock API handler - AFTER migration (some differences for testing)."""

    def _set_headers(self, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def _json_response(self, data: dict, status: int = 200):
        self._set_headers(status)
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if self.path.startswith("/v1/users"):
            # Same as before (should pass)
            self._json_response({
                "data": [
                    {"id": 1, "name": "Alice", "email": "alice@example.com", "createdAt": "2024-01-01", "updatedAt": time.strftime("%Y-%m-%d")},
                    {"id": 2, "name": "Bob", "email": "bob@example.com", "createdAt": "2024-01-02", "updatedAt": time.strftime("%Y-%m-%d")},
                ],
                "total": 2,
                "timestamp": time.time(),
            })
        elif self.path == "/v1/orders/123":
            # Same as before (should pass)
            self._json_response({
                "id": "123",
                "status": "delivered",
                "amount": 99.99,
                "processedAt": time.time(),
            })
        elif self.path == "/v1/products":
            # DIFFERENT! - Changed "count" to "total"
            self._json_response({
                "items": [
                    {"sku": "P001", "name": "Laptop", "price": 1000},
                    {"sku": "P002", "name": "Mouse", "price": 25},
                ],
                "total": 2,  # <-- changed from "count"
            })
        elif self.path == "/v1/status":
            # DIFFERENT! - Changed "code" value
            self._json_response({"status": "ok", "code": 201})  # <-- changed from 200
        else:
            self._json_response({"error": "Not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if self.path == "/v1/users":
            # Same as before (should pass)
            data = json.loads(body) if body else {}
            self._json_response({
                "id": 100,
                "name": data.get("name", "New User"),
                "email": data.get("email", "new@example.com"),
                "createdAt": time.strftime("%Y-%m-%d"),
                "updatedAt": time.strftime("%Y-%m-%d"),
            }, status=201)
        else:
            self._json_response({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        """Suppress logging."""
        pass


def run_server(port: int, label: str, handler_class):
    """Run mock server on given port."""
    server = HTTPServer((HOST, port), handler_class)
    print(f"{label} server running on http://{HOST}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{label} server stopped")
        server.server_close()


if __name__ == "__main__":
    import threading
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "both":
        # Run both servers in separate threads
        t1 = threading.Thread(target=run_server, args=(PORT_BEFORE, "Before", BeforeHandler), daemon=True)
        t2 = threading.Thread(target=run_server, args=(PORT_AFTER, "After", AfterHandler), daemon=True)
        t1.start()
        t2.start()
        print("Both servers running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping servers...")
    else:
        # Run single server
        port = PORT_BEFORE if len(sys.argv) < 2 else int(sys.argv[1])
        handler = BeforeHandler if port == PORT_BEFORE else AfterHandler
        run_server(port, f"Port {port}", handler)
