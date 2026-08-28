import os
import sqlite3
from flask import Flask, request, jsonify

DB_PASSWORD = os.getenv("DB_PASSWORD")
API_TOKEN = os.getenv("API_TOKEN")

app = Flask(__name__)

@app.route("/search", methods=["GET"])
def search_user():
    username = request.args.get("username")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = ?"  # secure: parameterized query
    cursor.execute(query, (username,))
    return jsonify(cursor.fetchall())

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)