---
title: WaifuGPT
emoji: 🌸
colorFrom: pink
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# 🌸 WaifuGPT Live2D — AI Waifu Companion

![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Live2D](https://img.shields.io/badge/Live2D-Cubism_4-ff69b4?style=for-the-badge)
![NVIDIA](https://img.shields.io/badge/NVIDIA-NIM-76b900?style=for-the-badge&logo=nvidia)
![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker)

A full-stack AI companion web application featuring a **Live2D animated waifu** that listens, responds, and expresses emotions in real time. Powered by a multimodal LLM (mistral-medium-3.5-128b via NVIDIA NIM), a Japanese TTS engine, and a Pixi.js Live2D renderer — all served from a single FastAPI backend.

---

## ✨ Key Features

* **Live2D Model Rendering:** Fully animated anime character with physics, idle motion, and dynamic expressions driven by AI emotion detection.
* **Multimodal AI Chat:** Send text or images — the AI understands both and responds in character as Nagisa Furukawa.
* **Bilingual Responses:** Every reply is delivered in both English and Japanese simultaneously.
* **Japanese TTS Voice:** Synthesized voice output using a custom VITS-based TTS model trained on anime speech.
* **Real-Time Lip Sync:** Web Audio API analyser drives the model's mouth parameter in sync with audio playback.
* **Emotion-Driven Expressions:** The model's face changes automatically based on the sentiment of each response (happy, sad, angry, embarrassed, surprised).
* **Head Tracking:** The model's eyes and head follow your cursor for an immersive feel.

---

## 🏗️ Architecture & Tech Stack

**Frontend**
* **Renderer:** Pixi.js v5 + pixi-live2d-display v0.3.1 (Cubism 4)
* **Live2D SDK:** Live2D Cubism Web Core
* **Audio:** Web Audio API (AudioContext + AnalyserNode for lip sync)
* **Styling:** Vanilla CSS with sakura-themed design system

**Backend (API & AI)**
* **Framework:** FastAPI (Python 3.12) + Uvicorn
* **LLM:** `mistral-medium-3.5-128b` via NVIDIA NIM API
* **TTS:** VITS-based multi-speaker synthesis (Japanese)
* **Audio Export:** SoundFile (WAV → base64)
* **Deployment:** Docker on HuggingFace Spaces

### 📂 Project Structure

```text
WaifuGPT/
├── backend/
│   ├── main.py                # FastAPI server, routes, TTS pipeline
│   ├── chatbot.py             # NVIDIA NIM API client, conversation history
│   ├── models.py              # VITS synthesizer model definition
│   ├── utils.py               # Checkpoint loading, hyperparameter helpers
│   ├── commons.py             # Shared utilities
│   ├── mel_proccessing.py     # Mel spectrogram processing
│   ├── attentions.py          # Attention modules
│   ├── modules.py             # Neural network modules
│   └── transforms.py         # Audio transforms
├── frontend/
│   ├── index.html             # Main app (Live2D + chat UI)
│   └── model/
│       └── majo/
│           ├── majo.model3.json        # Model config (expressions + motions)
│           ├── 魔女.moc3               # Rigged model binary (Git LFS)
│           ├── 魔女.physics3.json      # Physics simulation config
│           ├── 魔女.cdi3.json          # Display info
│           ├── 魔女.8192/             # High-res texture atlas (Git LFS)
│           │   ├── texture_00.png
│           │   └── texture_01.png
│           ├── Scene1.motion3.json    # Idle motion
│           └── expressions/
│               ├── happy.exp3.json
│               ├── sad.exp3.json
│               ├── angry.exp3.json
│               ├── embarrassed.exp3.json
│               ├── surprised.exp3.json
│               └── neutral.exp3.json
├── tts/
│   ├── config.json            # TTS model hyperparameters + speaker list
│   └── model.pth              # Pretrained VITS checkpoint (Git LFS)
├── text/                      # Text normalization & phonemizer modules
├── monotonic_align/           # Monotonic alignment search (Cython)
├── Dockerfile                 # Container definition for HuggingFace
├── requirements.txt
└── .gitattributes             # Git LFS tracking rules
```

---

## 🚀 Local Setup

### Prerequisites
* Python 3.12+
* Git LFS installed (`git lfs install`)
* NVIDIA NIM API key from [build.nvidia.com](https://build.nvidia.com)

### 1. Clone the Repository
```bash
git clone https://github.com/MinhQuan0716/waifugpt-live2d.git
cd waifugpt-live2d
```

### 2. Install Dependencies
```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```text
NVIDIA_API_KEY=nvapi-your-key-here
```

### 4. Run the Backend
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

### 5. Open the Frontend
The frontend is served automatically by FastAPI at:
```
http://localhost:8000
```

---

## 🧠 How It Works

1. **User Input:** Text or image is submitted via the chat panel.
2. **LLM Response:** FastAPI forwards the request to Kimi K2.6 (NVIDIA NIM) with a strict system prompt enforcing Nagisa's character and bilingual JSON output format.
3. **Emotion Detection:** A keyword-based classifier parses the English response to determine the emotional tone.
4. **TTS Synthesis:** The Japanese portion of the response is passed through the VITS TTS model to generate a WAV audio array.
5. **Response Delivery:** FastAPI returns `{ en, ja, audio (base64 WAV), emotion }` as a single JSON payload.
6. **Live2D Reaction:** The frontend sets the model expression, plays the audio, and drives lip sync via the Web Audio API analyser in real time.

```
User Input (text/image)
        ↓
   FastAPI /chat
        ↓
  NVIDIA NIM API (Kimi K2.6)
        ↓
  Parse JSON → EN + JA + emotion
        ↓
  VITS TTS → WAV audio
        ↓
  JSONResponse { en, ja, audio, emotion }
        ↓
  Frontend: expression + lip sync + chat bubble
```

---

## 🎭 Emotion → Expression Mapping

| Detected Emotion | Live2D Expression | Triggered By |
|-----------------|-------------------|--------------|
| `happy` | Smile eyes + mouth up | love, wonderful, happy, yay |
| `sad` | Brow down + mouth down | sorry, miss, cry, tears |
| `angry` | Furrowed brow | angry, stop, hate, upset |
| `embarrassed` | Blush expression | embarrass, blush, shy |
| `surprised` | Wide eyes | surprised, wow, oh no |
| `neutral` | Default face | everything else |

---

## 🔧 API Reference

### `POST /chat`
Send a message (with optional image) and receive a full response.

**Request:** `multipart/form-data`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | ✅ | User's message |
| `image` | file | ❌ | Optional image upload |

**Response:** `application/json`
```json
{
  "en": "English response text",
  "ja": "[JA]日本語の回答[JA]",
  "audio": "<base64 encoded WAV>",
  "emotion": "happy"
}
```

### `POST /reset`
Clear conversation history.

### `GET /health`
Check server status and speaker count.

---

## 🐳 Docker Deployment (HuggingFace Spaces)

The app is containerized for one-command deployment:

```bash
# Build locally
docker build -t waifugpt .
docker run -p 7860:7860 -e NVIDIA_API_KEY=your_key waifugpt
```

For HuggingFace Spaces, set `NVIDIA_API_KEY` under **Settings → Variables and secrets**.

---

## 🔮 Future Improvements

* **Memory System:** Persistent conversation history across sessions using a vector database.
* **Multiple Characters:** Support for swapping between different Live2D models and personalities.
* **Voice Input:** Microphone support with Whisper-based speech-to-text.
* **Better Lip Sync:** Phoneme-driven mouth shapes instead of amplitude-based approximation.
* **Mobile Support:** Responsive layout for phone and tablet viewports.

---

## ⚠️ Disclaimer

This project is for **educational and entertainment purposes only**. The Live2D model used is a free non-commercial asset. Not affiliated with Key, Visual Arts, or the Clannad franchise.

> *"Anpan... ダーリン、渚のこと、ずっと一緒にいてね。"* 🌸
