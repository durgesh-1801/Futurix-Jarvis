# Dependency Audit — Futurix Jarvis

This document lists the runtime and build-time Python package requirements for **Futurix Jarvis**, verifies open-source licenses, and documents NumPy 2.x compatibility.

---

## 1. Active Dependencies

| Package Name | Minimum Version | License | Category | Purpose |
| :--- | :---: | :---: | :---: | :--- |
| **PyQt6** | `>=6.6.0` | GPLv3 / Commercial | GUI | Native Windows desktop layout & widgets |
| **pyqtdarktheme** | `>=2.1.0` | MIT | GUI | Neon stylesheet styling |
| **langchain** | `>=0.3.0` | MIT | LLM | ReAct agent orchestration framework |
| **langchain-core** | `>=0.3.0` | MIT | LLM | Core prompts and model tool binds |
| **langchain-ollama** | `>=0.2.0` | MIT | LLM | Local ChatOllama interface bindings |
| **pypdf** | `*` | BSD-3-Clause | RAG | Extraction of raw text from PDF manuals |
| **SpeechRecognition**| `>=3.10.0` | BSD | Voice | Converts microphone audio to clean strings |
| **PyAudio** | `>=0.2.13` | MIT | Voice | Stream recording buffers for STT |
| **pyttsx3** | `>=2.90` | MPL 2.0 | Voice | SAPI5 voice text-to-speech engine |
| **psutil** | `>=5.9.0` | BSD-3-Clause | System | CPU, RAM, and process termination |
| **pyautogui** | `>=0.9.54` | BSD | System | Screen capturing and window dimensions |
| **python-dotenv** | `>=1.0.0` | BSD-3-Clause | Config | Loading configuration settings from `.env` |
| **httpx** | `>=0.27.0` | BSD-3-Clause | HTTP | Connecting to local Ollama endpoints |
| **chromadb** | `>=1.5.9` | Apache 2.0 | RAG | High-performance vector embeddings search |
| **numpy** | `>=1.26.0` | BSD-3-Clause | Math | Mathematical vector arrays |

---

## 2. Licensing Compliance

All third-party libraries use commercially permissive open-source licenses (MIT, BSD, Apache 2.0, MPL 2.0) suitable for deployment, with the exception of **PyQt6**:
- **PyQt6** uses **GPLv3**. If this application is distributed commercially as closed-source, a commercial license must be purchased from Riverbank Computing. For open-source projects, GPLv3 is fully compliant.

---

## 3. NumPy 2.x & ChromaDB Compatibility

- **Root Cause of Phase 2 Conflicts**:
  Earlier versions of ChromaDB (e.g. `< 0.5.1`) referenced the deprecated type attribute `np.float_`. NumPy 2.0 removed this attribute, leading to a startup crash when ChromaDB imported numpy:
  `AttributeError: module 'numpy' has no attribute 'float_'`.
- **Resolution**:
  - We updated `requirements.txt` to require `chromadb>=1.5.9`.
  - ChromaDB version 1.5.9 fully resolves the issue by referencing `np.float64` natively.
  - The application compiles and runs successfully under **NumPy 2.4.6** and **ChromaDB 1.5.9** with no environment regressions.
