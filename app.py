import sqlite3
from flask import Flask, request, jsonify

AWS_SECRET_KEY = "AKIAIOSFODNN7EXAMPLE_SECRET_KEY_FOR_TESTING"

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