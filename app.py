import os
import sqlite3
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file (for local dev)
load_dotenv()

# === Config ===
HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://router.huggingface.co/featherless-ai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json"
}

# Database path (change to "chat_history.db" for local dev if needed)
DB_PATH = "/data/chat_history.db"  # for Render persistent storage
# DB_PATH = "chat_history.db"  # for local testing

# === Initialize DB if it doesn't exist ===
def init_db():
    if not os.path.exists(DB_PATH):
        print("📦 Creating chat_history.db...")
        with sqlite3.connect(DB_PATH) as conn:
            with open("schema.sql", "r") as f:
                conn.executescript(f.read())
        print("✅ DB initialized.")

init_db()

# === Flask App ===
app = Flask(__name__)
CORS(app)  # Enable CORS for all origins (safe for dev)

# === Helper Functions ===

def get_recent_messages(chat_id, limit=5):
    """Retrieve the latest N messages for a conversation."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content FROM messages
            WHERE chat_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (chat_id, limit))
        rows = cursor.fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]


def save_message(chat_id, role, content):
    """Save a message to the database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (chat_id, role, content)
            VALUES (?, ?, ?)
        """, (chat_id, role, content))
        conn.commit()

# === API Route ===

@app.route("/api/doctor", methods=["POST"])
def doctor_chat():
    data = request.get_json()

    chat_id = data.get("chat_id")
    message = data.get("message")

    if not chat_id or not message:
        return jsonify({"error": "Missing chat_id or message"}), 400

    # Append vitals if available
    vitals = ""
    if data.get("heart_rate"): vitals += f"Heart rate: {data['heart_rate']} bpm. "
    if data.get("sugar_level"): vitals += f"Sugar: {data['sugar_level']} mg/dL. "
    if data.get("blood_pressure"): vitals += f"Blood pressure: {data['blood_pressure']}. "
    if data.get("temperature"): vitals += f"Temperature: {data['temperature']}°C. "
    if vitals:
        message += f"\n\nPatient vitals: {vitals.strip()}"

    # Save user message
    save_message(chat_id, "user", message)

    # Construct prompt for model
    messages = [{
        "role": "system",
        "content": (
            "You are a friendly, professional medical assistant. "
            "Speak casually and warmly like you're chatting with a patient. "
            "Keep answers short and clear unless more detail is needed."
        )
    }] + get_recent_messages(chat_id)

    payload = {
        "model": "mistralai/Mistral-7B-Instruct-v0.2",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 128
    }

    try:
        hf_response = requests.post(API_URL, headers=HEADERS, json=payload)
        hf_response.raise_for_status()  # raise if non-200

        response_data = hf_response.json()
        reply = response_data["choices"][0]["message"]["content"]

        # Save bot reply
        save_message(chat_id, "assistant", reply)

        return jsonify({
            "response": reply,
            "chat_id": chat_id,
            "status": "success"
        })

    except Exception as e:
        print("❌ Error:", e)
        print("🔴 HF Response:", hf_response.status_code if 'hf_response' in locals() else 'No response')
        print(hf_response.text if 'hf_response' in locals() else 'No response text')
        return jsonify({"error": "Something went wrong."}), 500


# === Local dev only ===
# Uncomment this if you're running locally
# if __name__ == "__main__":
#     app.run(debug=True, port=5000)
