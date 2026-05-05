import json
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
import urllib.parse
import os

DB_PATH = r"C:\Users\BjarneHøjgaard\OneDrive - Advisense AB\PRV\Nibe\cykler.db"

# ---------- Database ----------

def get_db_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cykel_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cykel_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            placering TEXT NOT NULL,
            medhjælpernavn TEXT,
            email TEXT,
            tlfnr TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    con.commit()
    con.close()

init_db()

# ---------- HTTP Server ----------

class CykelHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self._send_json({}, 200)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        # GET /cykel/<id>
        if path.startswith("/cykel/") and path.count("/") == 2:
            try:
                cykel_id = int(path.split("/")[2])
            except:
                return self._send_json({"error": "Ugyldigt ID"}, 400)

            con = get_db_connection()
            cur = con.cursor()
            cur.execute("""
                SELECT *
                FROM cykel_log
                WHERE cykel_id = ?
                ORDER BY datetime(timestamp) DESC, id DESC
                LIMIT 1
            """, (cykel_id,))
            row = cur.fetchone()
            con.close()

            if row is None:
                return self._send_json({"error": "Ingen data fundet"}, 404)

            return self._send_json(dict(row))

        # GET /cykler
        if path == "/cykler":
            con = get_db_connection()
            cur = con.cursor()
            result = []

            for cid in range(1, 41):
                cur.execute("""
                    SELECT cykel_id, status, placering, timestamp
                    FROM cykel_log
                    WHERE cykel_id = ?
                    ORDER BY datetime(timestamp) DESC, id DESC
                    LIMIT 1
                """, (cid,))
                row = cur.fetchone()

                if row:
                    result.append(dict(row))
                else:
                    result.append({
                        "cykel_id": cid,
                        "status": "ukendt",
                        "placering": "-",
                        "timestamp": "-"
                    })

            con.close()
            return self._send_json(result)
        # GET /cykel/<id>/historik
        if path.startswith("/cykel/") and path.endswith("/historik"):
            try:
                cykel_id = int(path.split("/")[2])
            except:
                return self._send_json({"error": "Ugyldigt ID"}, 400)

        con = get_db_connection()
        cur = con.cursor()
        cur.execute("""
                SELECT *
                FROM cykel_log
                WHERE cykel_id = ?
                ORDER BY datetime(timestamp) DESC, id DESC
                """, (cykel_id,))
        rows: list[Any] = cur.fetchall()
        con.close()

        historik = [dict(r) for r in rows]
        return self._send_json(historik)
        
        # Hvis ingen route matcher
        self._send_json({"error": "Endpoint ikke fundet"}, 404)

    def do_POST(self):
        if self.path != "/cykel":
            return self._send_json({"error": "Endpoint ikke fundet"}, 404)

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body)

        required = ["cykel_id", "status", "placering"]
        for f in required:
            if f not in data:
                return self._send_json({"error": f"Mangler felt: {f}"}, 400)

        cykel_id = data["cykel_id"]
        if not (1 <= int(cykel_id) <= 40):
            return self._send_json({"error": "cykel_id skal være 1–40"}, 400)

        con = get_db_connection()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO cykel_log (cykel_id, status, placering, medhjælpernavn, email, tlfnr, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            cykel_id,
            data["status"],
            data["placering"],
            data.get("medhjælpernavn"),
            data.get("email"),
            data.get("tlfnr"),
            datetime.now().isoformat(timespec="seconds")
        ))
        con.commit()
        new_id = cur.lastrowid
        con.close()

        return self._send_json({"message": "Ny registrering gemt", "id": new_id}, 201)


# ---------- Start server ----------

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), CykelHandler)
    print("Server kører på http://localhost:5000")
    server.serve_forever()