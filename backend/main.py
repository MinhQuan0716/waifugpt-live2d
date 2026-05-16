import os
import io
import random
import sys

import numpy as np
from typing import Optional, Union
import base64
import json
import re
from torch import no_grad, LongTensor
import torch
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, PARENT_DIR)
sys.path.insert(0, BASE_DIR)

from backend.chatbot import Chatbot
from backend.models import SynthesizerTrn
from text import text_to_sequence
import backend.utils
import librosa
import backend.commons
from backend.mel_proccessing import spectrogram_torch
from dotenv import load_dotenv
import soundfile as sf
import tempfile

load_dotenv()
limitation = os.getenv("SYSTEM") == "spaces"
device = "cuda" if torch.cuda.is_available() else "cpu"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')

# Initialize FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    global speakers, tts_fn, vc_fn
    speakers, tts_fn, vc_fn = tts_audio()
    print("Models loaded!")
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict this in production
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="fronted")
# Initialize chatbot
chatbot = Chatbot(
    model="mistralai/mistral-medium-3.5-128b",
    api_key=os.getenv("NVIDIA_API_KEY"),
    max_tokens=16384,
    temperature=0.7,
    top_p=1.0,
    stream=False,
    reasoning_effort= "high"
)

# Load TTS on startup

speakers, tts_fn, vc_fn = None, None, None

def parse_response(response):
    print("PARSING:", repr(response))
    if not response:
        return "Sorry darling!", ""
    try:
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        cleaned = re.sub(r"```(?:json)?", "", response).strip()
        match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
        if not match:
            return response, "[JA][JA]"
        data = json.loads(match.group())
    except (json.JSONDecodeError, AttributeError):
        return response, ""

    ja_text = data.get("JA", "")
    en_text = data.get("EN", "")
    ja_text = f"[JA]{ja_text}[JA]"
    return en_text, ja_text


def detect_emotion(text):
    text = text.lower()
    if any(w in text for w in ["happy", "love", "yay", "wonderful", "glad", "excited"]):
        return "happy"
    elif any(w in text for w in ["sorry", "sad", "miss", "cry", "tears"]):
        return "sad"
    elif any(w in text for w in ["angry", "stop", "no", "hate", "upset"]):
        return "angry"
    elif any(w in text for w in ["embarrass", "blush", "shy"]):
        return "embarrassed"
    return "neutral"


def audio_to_base64(sampling_rate, audio_array):
    buffer = io.BytesIO()
    sf.write(buffer, audio_array, sampling_rate, format="WAV")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def get_text(text, hps, is_symbol):
    text_norm = text_to_sequence(
        text, hps.symbols, [] if is_symbol else hps.data.text_cleaners
    )
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    text_norm = LongTensor(text_norm)
    return text_norm


def create_tts_fn(model, hps, speaker_ids):
    def tts_fn(text, speaker, speed, is_symbol):
        speaker_id = speaker_ids[speaker]
        stn_tst = get_text(text, hps, is_symbol)
        with no_grad():
            x_tst = stn_tst.unsqueeze(0).to(device)
            x_tst_lengths = LongTensor([stn_tst.size(0)]).to(device)
            sid = LongTensor([speaker_id]).to(device)
            audio = (
                model.infer(
                    x_tst,
                    x_tst_lengths,
                    sid=sid,
                    noise_scale=0.667,
                    noise_scale_w=0.8,
                    length_scale=1.0 / speed,
                )[0][0, 0]
                .data.cpu()
                .float()
                .numpy()
            )
        del stn_tst, x_tst, x_tst_lengths, sid
        return "Success", (hps.data.sampling_rate, audio)
    return tts_fn


def create_vc_fn(model, hps, speaker_ids):
    def vc_fn(original_speaker, target_speaker, input_audio):
        if input_audio is None:
            return "You need to upload an audio", None
        sampling_rate, audio = input_audio
        duration = audio.shape[0] / sampling_rate
        if limitation and duration > 30:
            return "Error: Audio is too long", None
        original_speaker_id = speaker_ids[original_speaker]
        target_speaker_id = speaker_ids[target_speaker]
        audio = (audio / np.iinfo(audio.dtype).max).astype(np.float32)
        if len(audio.shape) > 1:
            audio = librosa.to_mono(audio.transpose(1, 0))
        if sampling_rate != hps.data.sampling_rate:
            audio = librosa.resample(audio, orig_sr=sampling_rate, target_sr=hps.data.sampling_rate)
        with no_grad():
            y = torch.FloatTensor(audio)
            y = y.unsqueeze(0)
            spec = spectrogram_torch(y, hps.data.filter_length, hps.data.sampling_rate,
                                     hps.data.hop_length, hps.data.win_length, center=False).to(device)
            spec_lengths = LongTensor([spec.size(-1)]).to(device)
            sid_src = LongTensor([original_speaker_id]).to(device)
            sid_tgt = LongTensor([target_speaker_id]).to(device)
            audio = (model.voice_conversion(spec, spec_lengths, sid_src=sid_src, sid_tgt=sid_tgt)
                     [0][0, 0].data.cpu().float().numpy())
        del y, spec, spec_lengths, sid_src, sid_tgt
        return "Success", (hps.data.sampling_rate, audio)
    return vc_fn


def tts_audio():
    config_path = os.path.join(PARENT_DIR, "tts", "config.json")
    model_path = os.path.join(PARENT_DIR, "tts", "model.pth")
    hps = utils.get_hparams_from_file(config_path)
    model = SynthesizerTrn(
        len(hps.symbols),
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        n_speakers=hps.data.n_speakers,
        **hps.model,
    )
    utils.load_checkpoint(model_path, model, None)
    model.eval().to(device)
    if isinstance(hps.speakers, utils.HParams):
        speakers, speaker_ids = zip(*hps.speakers.items())
    else:
        speaker_ids = [sid for sid, name in enumerate(hps.speakers) if name != "None"]
        speakers = [name for sid, name in enumerate(hps.speakers) if name != "None"]
    return speakers, create_tts_fn(model, hps, speaker_ids), create_vc_fn(model, hps, speaker_ids)


# ── API Routes ──────────────────────────────────────────────

@app.post("/chat")
async def chat(
    text: str = Form(...),
    image: Union[UploadFile, None] = File(default=None),
):
    image_path = None
    if image is not None and image.filename:  # ← check is not None explicitly
        content = await image.read()
        if content:
            ext = image.filename.split(".")[-1] if "." in image.filename else "png"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
            tmp.write(content)
            tmp.close()
            image_path = tmp.name

    raw_response = chatbot.generate_response(image_path=image_path, text=text)
    print("RAW RESPONSE:", repr(raw_response))

    en_text, ja_text = parse_response(raw_response)
    emotion = detect_emotion(en_text)

    audio_b64 = None
    if ja_text and tts_fn:
        status, audio_data = tts_fn(ja_text, 73, 1.0, False)
        if status == "Success":
            sampling_rate, audio_array = audio_data
            audio_b64 = audio_to_base64(sampling_rate, audio_array)

    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    return JSONResponse({
        "en": en_text,
        "ja": ja_text,
        "audio": audio_b64,
        "emotion": emotion,
    })


@app.post("/reset")
async def reset():
    chatbot.history = []
    return {"status": "ok"}

@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
@app.get("/health")
async def health():
    return {"status": "ok", "speakers": len(speakers) if speakers else 0}