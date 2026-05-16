# WaifuGPT-3D — Frontend Setup

## Directory Structure
```
frontend/
├── index.html              ← main app
└── model/
    └── majo/
        ├── majo.model3.json       ← updated config (with expressions + motions)
        ├── 魔女.moc3              ← copy from original zip
        ├── 魔女.physics3.json     ← copy from original zip
        ├── 魔女.cdi3.json         ← copy from original zip
        ├── 魔女.8192/             ← copy texture folder from original zip
        │   ├── texture_00.png
        │   └── texture_01.png
        ├── Scene1.motion3.json    ← copy from original zip
        └── expressions/
            ├── happy.exp3.json
            ├── sad.exp3.json
            ├── angry.exp3.json
            ├── embarrassed.exp3.json
            ├── surprised.exp3.json
            └── neutral.exp3.json
```

## Setup Steps

### 1. Copy model files from the zip
Extract `魔女.zip` and copy these into `frontend/model/majo/`:
- `魔女.moc3`
- `魔女.physics3.json`
- `魔女.cdi3.json`
- `魔女.8192/` (entire folder with textures)
- `Scene1.motion3.json`

### 2. Start the backend
```bash
cd WaifuGPT_API
uvicorn main:app --reload --port 8000
```

### 3. Serve the frontend (must use a local server, not file://)
```bash
cd frontend
npx serve .
# or
python -m http.server 5500
```

Then open: http://localhost:5500

### Why a local server?
Browsers block loading .moc3 and texture files from `file://` due to CORS.
Always serve via HTTP even for local development.

## Expression Mapping
| Emotion     | Expression File       |
|-------------|----------------------|
| happy       | h.exp3.json (Param69)|
| sad         | ku.exp3.json         |
| angry       | sq.exp3.json         |
| embarrassed | yj.exp3.json (Param66)|
| surprised   | hdj.exp3.json        |
| neutral     | (no expression)      |
