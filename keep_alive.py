from flask import Flask
import threading
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8000)

def start():
    threading.Thread(target=run).start()
