from ai_agent_response import agent_response
from flask import Flask, render_template, request, jsonify
from load_file_from_url import load_file_from_url
import sqlite3

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")
    else:
        # Handle URL submission without page refresh
        if "documentUrl" in request.form:
            url = request.form.get("documentUrl")
            token = request.form.get("oauthToken")  # Get token if provided
            print(f"URL: {url}, Token: {token}")
            if token:
                result = load_file_from_url(url, token)  # Pass token if present
            else:
                result = load_file_from_url(url)  # No token, use original call
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"result": result})
            else:
                return render_template("index.html", result=result)
        # Handle chat messages
        elif "query" in request.form:
            query = request.form.get("query")
            result = agent_response(query)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"result": result})
            else:
                return render_template("index.html", result=result)
        else:
            return render_template("index.html")
        
@app.route("/history", methods=["GET"])
def history():
    try:
        conn = sqlite3.connect("memory.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_query, final_answer, timestamp FROM memory_logs ORDER BY timestamp ASC")
        interactions = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError:
        interactions = []  # If database or table doesn’t exist, return empty list
    return render_template("history.html", interactions=interactions)

if __name__ == "__main__":
    app.run(debug=True)