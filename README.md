# HSKK_teacher

This template should help get you started developing with Vue 3 in Vite.

## Quick Start

### Backend

Run the Flask ASR server on port `5001`:

```sh
PORT=5001 FLASK_APP=server/python_asr_server.py flask run --host=0.0.0.0 --port=5001
```

This exposes the ASR API at `http://localhost:5001/api/asr`.

### Frontend

Start the Vite dev server and point it to the local ASR endpoint:

```sh
VITE_ASR_ENDPOINT=http://localhost:5001/api/asr npm run dev

打包/同源部署时可不设置 VITE_ASR_ENDPOINT，前端默认请求 `/api/asr`、`/api/diagnose`、`/api/gram-check`。
Electron 打包应用使用 `file://` 打开页面时，会自动回退到 `http://localhost:5001/api/asr`。
```

## Electron App (Desktop)

This project can be packaged as a desktop app (Windows/macOS) by bundling the
Vue UI and a standalone Python server binary.

### Dev (Electron + Vite)

1) Install deps:

```sh
npm install
```

2) Run the desktop app:

```sh
npm run app:dev
```

This starts Vite on `http://localhost:5173` and launches Electron pointing to it.

### Build (Windows/macOS)

You must build the Python server binary on each target OS.

1) Create a Python environment and install backend deps:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
pip install pyinstaller
```

2) Build the Vue UI + Python server binary + Electron app:

```sh
npm run build:app
```

The packaged installers will be in `dist-electron/`.
The macOS installer DMG is located under `dist-electron/` (e.g. `dist-electron/*.dmg`).

### Environment Variables

The Python server uses `DASHSCOPE_API_KEY`. You can set it before launching the
app, or add it to your shell profile:

```sh
export DASHSCOPE_API_KEY=sk-xxx
```

## Project Setup (frontend)

```sh
npm install
```
