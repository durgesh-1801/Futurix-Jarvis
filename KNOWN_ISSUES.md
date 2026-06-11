# Known Issues and Limitations — Futurix Jarvis

This document details the known technical limitations, installation edge cases, and hardware overhead issues in **Futurix Jarvis** along with recommendations, workarounds, and configuration mitigation strategies.

---

## 1. PyAudio Installation Failure on Windows

### Description
The `pyaudio` package requires compiling native C++ bindings for the PortAudio library. If the host machine does not have the Microsoft Visual C++ Build Tools installed, running `pip install pyaudio` or `pip install -r requirements.txt` will fail with compiler errors (e.g., `error: Microsoft Visual C++ 14.0 or greater is required`).

### Workarounds & Mitigation
- **Method A: Use Pre-compiled Wheel (Recommended)**
  1. Download the pre-compiled `.whl` file corresponding to your Python version (e.g., Python 3.12 64-bit -> `PyAudio‑0.2.13‑cp312‑cp312‑win_amd64.whl`) from a reliable wheel repository.
  2. Install it directly:
     ```cmd
     .venv\Scripts\pip.exe install PyAudio-0.2.13-cp312-cp312-win_amd64.whl
     ```
- **Method B: Use pipwin**
  `pipwin` acts as a package manager for Windows, automatically fetching pre-compiled binaries:
  ```cmd
  .venv\Scripts\pip.exe install pipwin
  .venv\Scripts\pipwin.exe install pyaudio
  ```
- **Method C: Install Build Tools**
  Download the [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and select the "Desktop development with C++" workload during installation, then re-run `pip install pyaudio`.

---

## 2. High Screen-Capture CPU Cost & DPI Coordinates Mismatch

### Description
The vision analysis and screen capturing features rely on `pyautogui` and `PIL.ImageGrab`. On high-resolution displays (e.g., 1080p, 1440p, or 4K) or multi-monitor setups:
1. **CPU Overhead**: Capturing screenshots at high frequencies (e.g., in loops) incurs significant CPU and memory rendering costs.
2. **DPI Scaling Coordinates Mismatch**: Windows high-DPI scaling (e.g., 125% or 150%) causes coordinate mismatches where click positions or bounding boxes in screen captures do not line up with the actual OS coordinates.

### Mitigations
- **Event-Driven Screenshotting**: Jarvis does not capture screenshots continuously. Screenshots are only taken on-demand when the user explicitly requests vision analysis or when an error diagnostic command is triggered.
- **Qt High-DPI Scaling Enablement**: The application sets `QT_ENABLE_HIGHDPI_SCALING = "1"` at startup to auto-scale the PyQt6 UI, but native automation mouse/keyboard commands must divide coordinates by `(scaling_factor / 100)` when interfacing with pyautogui.
- **Targeted Capturing**: Future versions will use the Windows Graphics Capture (WGC) API via the `pydirectinput` or native bindings to capture single windows instead of the entire desktop layout, reducing the capture buffer size.

---

## 3. Large Ollama Weights Download Size & High VRAM/RAM Usage

### Description
Jarvis uses local LLMs via Ollama to ensure complete data privacy. However:
1. **Large Models**: The default orchestrator LLM (e.g., `llama3` or `qwen2.5`) is 4.7GB, the vision model (`llava`) is 4.7GB, and the embeddings model (`nomic-embed-text`) is 278MB.
2. **Cold-Start Latency**: The first prompt after startup takes 10–20 seconds to execute because Ollama must load the model weights into GPU VRAM (or CPU RAM if no compatible GPU is found).
3. **Out of Memory (OOM)**: Systems with less than 16GB of system RAM or less than 6GB of VRAM will experience severe slowdowns, context pruning, or model crashes due to paging out to disk.

### Recommendations
- **Model Alternatives**: For lower-end machines, change the settings in `.env` to use lightweight models:
  - Orchestration LLM: `qwen2.5:1.5b` or `qwen2.5:3b` instead of `llama3`.
  - Embeddings: Keep `nomic-embed-text` as it is lightweight (278MB).
- **Ollama Keep-Alive Configuration**: Set the environment variable `OLLAMA_NUM_PARALLEL=1` and configure `OLLAMA_KEEP_ALIVE=24h` to keep models cached in VRAM and avoid cold-start delays on subsequent interactions.

---

## 4. ChromaDB SQLite Version Mismatch on Windows

### Description
ChromaDB requires `sqlite3` version `3.35.0` or higher to use advanced vector storage indexing. By default, older Python installations on Windows may ship with an older `sqlite3.dll` (e.g., `3.34.x`), leading to startup failures:
`RuntimeError: Your system's version of sqlite3 is too old. Chroma requires sqlite3 >= 3.35.0`.

### Workarounds & Mitigation
- **Automatic Fallback (Built-in)**: Jarvis's `VectorStoreFactory` detects this runtime error and automatically falls back to an `InMemoryVectorStore` with SQLite keyword/TF-IDF scoring, allowing the application to run without crashing.
- **Manual DLL Upgrade**:
  1. Download the pre-compiled SQLite DLL (version 3.35+ / latest) for Windows x64 from the official SQLite website.
  2. Replace the `sqlite3.dll` inside your Python installation directory (e.g., `C:\Python312\DLLs\sqlite3.dll` or inside your `.venv\DLLs\`).
- **Binary Extension**: Alternatively, install the `pysqlite3-binary` package, although native DLL replacement is the most robust fix on Windows.

---

## 5. Concurrent SQLite Database Lockups

### Description
If multiple instances of Futurix Jarvis are opened concurrently, or if multiple background worker threads try to write to the main conversation/task SQLite database (`data/jarvis.db`) at the exact same millisecond, the database can throw a `sqlite3.OperationalError: database is locked`.

### Safeguards in Place
- **WAL (Write-Ahead Logging) Mode**: The database manager initializes the database with `PRAGMA journal_mode=WAL;`, which allows concurrent readers and prevents read-write blocking.
- **Thread Locks**: All database write operations in `db_manager.py` are wrapped in a Python `threading.Lock()` to serialize access across the Qt worker threads.
- **Single Instance Enforcement (Future)**: Release builds will implement a PyQt single-instance socket lock to prevent users from launching overlapping processes sharing the same database file.
