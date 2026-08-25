import os
import sqlite3
from flask import Flask, request, jsonify

DB_PASSWORD = os.getenv("Pr0d_Db_P@ssw0rd_202_Secure")
API_TOKEN = os.getenv("a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0")

app = Flask(__name__)

@app.route("/search", methods=["GET"])
def search_user():
    username = request.args.get("username")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE username = '{username}'"  # flaw: SQL injection
    cursor.execute(query)
    return jsonify(cursor.fetchall())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)