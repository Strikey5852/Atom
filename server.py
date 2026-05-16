import os
import threading

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
@app.route("/health")
def health():
    """Health-check endpoint that Render can ping to keep the bot alive."""
    return jsonify({"status": "ok"})


def run():
    """Start Flask on the port Render provides (default 8080)."""
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def start():
    """Launch the Flask server in a background daemon thread."""
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print(f"[Server] Flask health-check server started on port {os.getenv('PORT', 8080)}")