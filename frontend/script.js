// ── Config ──────────────────────────────────────────────────
const API_BASE = "";
const MODEL_PATH = "./frontend/model/majo/majo.model3.json";

// ── State ───────────────────────────────────────────────────
let currentModel = null;
let pendingImage = null;
let isLoading = false;
let lipSyncInterval = null;
let audioCtx = null;
let audioSrc = null;
let analyser = null;

// ── NEW: Memory State ────────────────────────────────────────
const MEMORY_KEY = "nagisa_memory";
let messagesSinceLastSummary = 0;
const SUMMARY_EVERY = 3; // summarize every N user messages

function getDefaultMemory() {
  return {
    user_name: "darling",
    facts: [],
    relationship_level: 1,
    last_seen: null,
    mood_history: [],
  };
}

function readMemoryFromStorage() {
  try {
    const raw = localStorage.getItem(MEMORY_KEY);
    return raw ? JSON.parse(raw) : getDefaultMemory();
  } catch {
    return getDefaultMemory();
  }
}

function writeMemoryToStorage(blob) {
  try {
    blob.last_seen = new Date().toISOString().split("T")[0]; // YYYY-MM-DD
    localStorage.setItem(MEMORY_KEY, JSON.stringify(blob));
  } catch (e) {
    console.warn("Could not save memory to localStorage:", e);
  }
}

async function loadMemory() {
  const blob = readMemoryFromStorage();
  try {
    await fetch(API_BASE + "/load-memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(blob),
    });
    console.log("Memory loaded into backend:", blob);
  } catch (e) {
    console.warn("Could not load memory into backend:", e);
  }
}

async function maybeSummarizeMemory() {
  messagesSinceLastSummary++;
  if (messagesSinceLastSummary < SUMMARY_EVERY) return;
  messagesSinceLastSummary = 0;

  try {
    const res = await fetch(API_BASE + "/summarize-memory", { method: "POST" });
    if (!res.ok) return;
    const updatedBlob = await res.json();
    writeMemoryToStorage(updatedBlob);
    console.log("Memory updated:", updatedBlob);
  } catch (e) {
    console.warn("Memory summarization failed:", e);
  }
}

// ── NEW: Track mood in memory ─────────────────────────────────
function trackMood(emotion) {
  const blob = readMemoryFromStorage();
  blob.mood_history = [...(blob.mood_history || []), emotion].slice(-10);
  writeMemoryToStorage(blob);
}
// ── Name Capture ─────────────────────────────────────────────
async function checkAndCaptureName() {
  const blob = readMemoryFromStorage();

  // Already named — skip
  if (blob.user_name && blob.user_name.toLowerCase() !== "darling") return;

  // Show modal
  const modal = document.getElementById("name-modal");
  const input = document.getElementById("name-input");
  const btn = document.getElementById("name-submit");
  modal.classList.remove("hidden");
  input.focus();

  async function submitName() {
    const name = input.value.trim();
    if (!name) return;

    // Save to localStorage
    blob.user_name = name;
    writeMemoryToStorage(blob);

    // Re-send updated blob to backend
    await loadMemory();

    // Hide modal
    modal.classList.add("hidden");

    // Nagisa greets them by name
    triggerNamedGreeting(name);
  }

  btn.addEventListener("click", submitName);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitName();
  });
}

function triggerNamedGreeting(name) {
  // Replace the default greeting message with a personalized one
  document.getElementById("messages").innerHTML = `
    <div class="msg bot">
      <div class="msg-bubble">${name}ダーリン～！渚はずっと待ってたよ♡</div>
      <div class="msg-ja">Nagisa has been waiting for you, ${name} darling~ ♡</div>
    </div>`;
}
// ── END Name Capture ──────────────────────────────────────────
// ── END NEW ──────────────────────────────────────────────────

// ── Live2D Setup ────────────────────────────────────────────
const { Live2DModel } = PIXI.live2d;

const stage = document.querySelector(".stage");
const app = new PIXI.Application({
  view: document.getElementById("live2d-canvas"),
  autoStart: true,
  width: stage.offsetWidth,
  height: stage.offsetHeight,
  transparent: true,
  antialias: true,
});

app.renderer.on("resize", () => {
  app.renderer.resize(stage.offsetWidth, stage.offsetHeight);
});

async function loadModel() {
  setLoadingProgress(20);
  try {
    console.log("Loading model from:", MODEL_PATH);

    const model = await Live2DModel.from(MODEL_PATH, {
      autoInteract: false,
      onLoad: () => console.log("Model loaded!"),
      onError: (e) => console.error("Model error:", e),
    });

    console.log("Model object:", model);
    console.log("Internal model:", model.internalModel);

    setLoadingProgress(70);
    app.stage.addChild(model);

    await new Promise((resolve) => requestAnimationFrame(resolve));
    const stageW = app.screen.width;
    const stageH = app.screen.height;

    const modelW = model.internalModel?.originalWidth || model.width;
    const modelH = model.internalModel?.originalHeight || model.height;

    const scale = Math.min(stageW / modelW, stageH / modelH) * 0.75;
    model.scale.set(scale);
    model.anchor.set(0.5, 0.5);
    model.x = stageW / 2;
    model.y = stageH / 2 + stageH * 0.05;

    model.motion("Idle", 0, MotionPriority.IDLE);

    currentModel = model;
    window.__nagisa = currentModel;

    document.querySelector(".stage").addEventListener("mousemove", (e) => {
      if (!currentModel) return;
      const rect = document.querySelector(".stage").getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = ((e.clientY - rect.top) / rect.height) * 2 - 1;
      try {
        currentModel.internalModel.coreModel.setParameterValueById("ParamAngleX", x * 30);
        currentModel.internalModel.coreModel.setParameterValueById("ParamAngleY", -y * 30);
        currentModel.internalModel.coreModel.setParameterValueById("ParamBodyAngleX", x * 10);
      } catch (e) {}
    });

    document.getElementById("live2d-canvas").addEventListener("webglcontextlost", (e) => {
      console.error("WebGL context lost!", e);
      e.preventDefault();
    }, false);

    document.getElementById("live2d-canvas").addEventListener("webglcontextrestored", () => {
      console.log("WebGL context restored");
      loadModel();
    }, false);

    setLoadingProgress(100);
    setTimeout(() => {
      document.getElementById("loading").classList.add("hidden");
    }, 500);

  } catch (err) {
    console.error("Failed to load Live2D model:", err);
    document.querySelector(".loading-sub").textContent =
      "⚠ Model load failed. Check console & model path.";
  }
}

function setLoadingProgress(pct) {
  document.getElementById("loading-fill").style.width = pct + "%";
}

const MotionPriority = { IDLE: 1, NORMAL: 2, FORCE: 3 };

window.addEventListener("resize", () => {
  if (!currentModel) return;
  const stageW = app.renderer.width;
  const stageH = app.renderer.height;
  const scale = Math.min(
    stageW / (currentModel.width / currentModel.scale.x),
    stageH / (currentModel.height / currentModel.scale.y)
  ) * 0.85;
  currentModel.scale.set(scale);
  currentModel.x = stageW / 2;
  currentModel.y = stageH / 2 + stageH * 0.05;
});

// ── Expression Control ───────────────────────────────────────
function setExpression(emotion) {
  document.getElementById("emotion-badge").textContent = emotion;
  if (!currentModel) return;
  try {
    currentModel.expression(emotion);
  } catch (e) {
    console.warn("Expression not found:", emotion);
  }
}

// ── Lip Sync ─────────────────────────────────────────────────
function startLipSync(audioEl) {
  if (!currentModel) return;
  if (!audioCtx) {
    audioCtx = new AudioContext();
    audioSrc = audioCtx.createMediaElementSource(audioEl);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    audioSrc.connect(analyser);
    analyser.connect(audioCtx.destination);
  }

  if (audioCtx.state === "suspended") audioCtx.resume();

  const data = new Uint8Array(analyser.frequencyBinCount);

  function tick() {
    if (audioEl.paused || audioEl.ended) {
      setMouth(0);
      return;
    }
    requestAnimationFrame(tick);
  }
  tick();
}

function setMouth(value) {
  if (!currentModel) return;
  try {
    const clamped = Math.max(0, Math.min(1, value));
    currentModel.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", clamped);
    currentModel.internalModel.coreModel.setParameterValueById("ParamMouthForm", 0);
  } catch (e) {
    console.error("Mouth error:", e);
  }
}

// ── Audio Playback ────────────────────────────────────────────
function playAudio(base64Wav, onEnd) {
  const audioEl = document.getElementById("tts-audio");
  const audioBar = document.getElementById("audio-bar");

  audioEl.src = "data:audio/wav;base64," + base64Wav;
  audioEl.load();
  audioBar.classList.add("visible");

  audioEl.oncanplaythrough = async () => {
    if (audioCtx && audioCtx.state === "suspended") await audioCtx.resume();
    try {
      await audioEl.play();
      startLipSync(audioEl);
    } catch (e) {
      console.warn("Autoplay blocked:", e);
      audioBar.classList.remove("visible");
      if (onEnd) onEnd();
    }
  };

  audioEl.onended = () => {
    audioBar.classList.remove("visible");
    setMouth(0);
    if (onEnd) onEnd();
  };
}

// ── Chat UI ───────────────────────────────────────────────────
function appendMessage(role, enText, jaText) {
  const msgs = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "bot");

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = enText;
  div.appendChild(bubble);

  if (jaText && role === "bot") {
    const ja = document.createElement("div");
    ja.className = "msg-ja";
    ja.textContent = jaText.replace(/\[JA\]/g, "").trim();
    div.appendChild(ja);
  }

  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function setTyping(visible) {
  document.getElementById("typing").classList.toggle("visible", visible);
  const msgs = document.getElementById("messages");
  msgs.scrollTop = msgs.scrollHeight;
}

// ── Send Message ──────────────────────────────────────────────
async function sendMessage() {
  if (isLoading) return;

  const input = document.getElementById("text-input");
  const text = input.value.trim();
  if (!text && !pendingImage) return;

  isLoading = true;
  document.getElementById("send-btn").disabled = true;

  appendMessage("user", text + (pendingImage ? " 🖼️" : ""), null);
  input.value = "";
  input.style.height = "auto";

  const imgFile = pendingImage;
  pendingImage = null;
  document.getElementById("image-preview").classList.remove("visible");

  setTyping(true);

  // Pre-create bot bubble so we can fill it progressively
  const msgs = document.getElementById("messages");
  const botDiv = document.createElement("div");
  botDiv.className = "msg bot";
  const botBubble = document.createElement("div");
  botBubble.className = "msg-bubble";
  botBubble.textContent = "";
  const botJa = document.createElement("div");
  botJa.className = "msg-ja";
  botJa.textContent = "";
  botDiv.appendChild(botBubble);
  botDiv.appendChild(botJa);
  // Don't append yet — wait for text event

  try {
    const form = new FormData();
    form.append("text", text);
    if (imgFile) form.append("image", imgFile);

    const res = await fetch(API_BASE + "/chat-stream", {
      method: "POST",
      body: form,
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // keep incomplete chunk

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        let event;
        try { event = JSON.parse(raw); }
        catch { continue; }

        // ── Phase 1: text arrives ──────────────────────────
        if (event.type === "text") {
          setTyping(false);
          setExpression(event.emotion || "neutral");
          trackMood(event.emotion || "neutral");

          // Now append the bubble
          botBubble.textContent = event.en;
          botJa.textContent = (event.ja || "").replace(/\[JA\]/g, "").trim();
          msgs.appendChild(botDiv);
          msgs.scrollTop = msgs.scrollHeight;

          maybeSummarizeMemory();
        }

        // ── Phase 2: audio arrives ─────────────────────────
        if (event.type === "audio" && event.audio) {
          playAudio(event.audio);
        }

        if (event.type === "error") {
          setTyping(false);
          appendMessage("bot", "⚠ " + event.message, null);
        }
      }
    }

  } catch (err) {
    setTyping(false);
    appendMessage("bot", "⚠ Could not reach the server. Is the backend running?", null);
    console.error(err);
  } finally {
    isLoading = false;
    document.getElementById("send-btn").disabled = false;
  }
}

// ── Reset ─────────────────────────────────────────────────────
async function resetChat() {
  try {
    await fetch(API_BASE + "/reset", { method: "POST" });
  } catch (e) {}

  document.getElementById("messages").innerHTML = `
    <div class="msg bot">
      <div class="msg-bubble">おかえり、ダーリン！今日はどうだった？</div>
      <div class="msg-ja">Welcome home, darling! How was your day?</div>
    </div>`;
  setExpression("neutral");

  // ── NEW: Force a memory save on reset so last_seen updates ──
  const blob = readMemoryFromStorage();
  writeMemoryToStorage(blob);
  // ── END NEW ─────────────────────────────────────────────────
}

// ── Event Listeners ───────────────────────────────────────────
document.getElementById("send-btn").addEventListener("click", sendMessage);

document.getElementById("text-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.getElementById("text-input").addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 100) + "px";
});

document.getElementById("reset-btn").addEventListener("click", resetChat);

document.getElementById("img-btn").addEventListener("click", () => {
  document.getElementById("file-input").click();
});

document.getElementById("file-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  pendingImage = file;
  const reader = new FileReader();
  reader.onload = (ev) => {
    document.getElementById("preview-img").src = ev.target.result;
    document.getElementById("image-preview").classList.add("visible");
  };
  reader.readAsDataURL(file);
  e.target.value = "";
});

document.getElementById("preview-remove").addEventListener("click", () => {
  pendingImage = null;
  document.getElementById("image-preview").classList.remove("visible");
});

// ── Boot ──────────────────────────────────────────────────────
loadMemory(); // fire early so backend is briefed ASAP
loadModel().then(() => {
  checkAndCaptureName(); // only show modal after loading screen is gone
});
// ── END NEW ──────────────────────────────────────────────────