# Futurix Jarvis — Testing and Verification Guide

This document details the installation verification, functional test cases, edge cases, and known system limitations of **Futurix Jarvis**. It serves as the primary verification plan for stability and correctness.

---

## 1. Installation Verification

Follow these checks to ensure the host system is properly configured before running the assistant.

### 1.1 Python and Dependencies
1. **Python Version**: Ensure Python 3.12 or higher is installed:
   ```cmd
   python --version
   ```
2. **Requirements Installation**: Verify all dependencies are installed cleanly into a virtual environment:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **PyAudio Check**: Since PyAudio requires native bindings, confirm it compiles or installs successfully.
   - If it fails, run:
     ```cmd
     pip install pipwin
     pipwin install pyaudio
     ```
   - Or install a pre-compiled wheel for Windows.

### 1.2 Ollama Verification
1. Confirm Ollama is running locally:
   ```cmd
   curl http://localhost:11434/
   ```
   (Should return `"Ollama is running"`)
2. Pull the default active model (e.g., `llama3` or `qwen2.5` as set in `.env`):
   ```cmd
   ollama pull llama3
   ```
3. Verify downloaded models list:
   ```cmd
   ollama list
   ```

### 1.3 Database Setup
- On first launch, the application creates an SQLite database at `C:\Users\user\.gemini\antigravity-ide\scratch\futurix_jarvis\data\jarvis.db` (or as configured in `.env`).
- Verify that `jarvis.db` and its companion files `jarvis.db-wal` / `jarvis.db-shm` are created.

---

## 2. Functional Test Cases

Run the following test scenarios to verify core features.

### 2.1 UI and Styling
- **Test Case 1: Startup Theme**
  - Run `python main.py`.
  - Verify that the window launches with the premium dark theme (vibrant blue neon elements, modern font typography, styled input boxes).
- **Test Case 2: Scrolling Chat History**
  - Type 15 consecutive messages.
  - Verify that the chat area scrolls down automatically to keep the latest exchange visible.

### 2.2 Local LLM Inference and Memory
- **Test Case 3: Prompt Interaction**
  - Type: *"Explain the concept of quantum computing in one sentence."*
  - Verify streaming token display.
- **Test Case 4: Context Retention**
  - Step 1: Type: *"My name is Alice."*
  - Step 2: Type: *"What is my name?"*
  - Verify response: *"Your name is Alice."* (Confirms history context injection).
- **Test Case 5: Conversation Persistence**
  - Close the app. Open it again.
  - Select the previous conversation from the History Sidebar.
  - Ask: *"Do you remember my name?"*
  - Verify that the database loaded history correctly and the LLM recalls "Alice".

### 2.3 Desktop Automation (Tools)
- **Test Case 6: Launch Applications**
  - Type: *"Open Notepad"* or *"Launch Calculator"*.
  - Verify the respective desktop utility launches.
- **Test Case 7: Terminate Applications**
  - Type: *"Close Notepad"*.
  - Verify Notepad is closed safely (via `psutil`).
- **Test Case 8: Web Search**
  - Type: *"Search Google for space exploration breakthroughs"*.
  - Verify default web browser opens with Google search results.

### 2.4 Document RAG Knowledge Base
- **Test Case 9: Ingestion**
  - Place a text file containing: *"Futurix Jarvis code activation key is FJ-992-ALPHA."* in the `knowledge_base/` folder.
  - Type: *"Ingest knowledge base"* or call the tool.
  - Verify output: *"Ingested [filename] -> Chunks added."*
- **Test Case 10: Retreival and Q&A**
  - Type: *"What is the code activation key?"*
  - Verify that the RAG service matches the document chunk and the LLM responds: *"The code activation key is FJ-992-ALPHA."*

### 2.5 Coding Agent Mode
- **Test Case 11: Git Inspection**
  - Type: *"Check git status of the project"*.
  - Verify output prints modified files / untracked files.
- **Test Case 12: Code File Generation**
  - Type: *"Create a python script named test_calc.py that does basic math"*.
  - Verify file creation inside workspace and validation of contents.

---

## 3. Edge Cases

Verify stability under error conditions and boundary cases.

### 3.1 Ollama Offline (Graceful Fallback)
1. Terminate the local Ollama process.
2. Launch the application.
3. Verify:
   - GUI displays "OFFLINE" indicator.
   - Status message says: *"Ollama is offline. Non-LLM features are active in Offline Fallback mode."*
4. Type: *"Open Calculator"*.
   - Verify: The app maps the request via offline keyword matching and opens the Calculator successfully.
5. Type: *"Search Google for weather"*.
   - Verify: The browser opens Google.
6. Type: *"What is the speed of light?"*.
   - Verify response: *"I am currently offline. I can assist with local desktop automation commands (opening apps, searching the web, system controls), but general question-answering requires Ollama to be running."*

### 3.2 Voice Initialization Safety (PyAudio Missing)
1. Uninstall PyAudio / SpeechRecognition: `pip uninstall -y pyaudio`
2. Run `python main.py`.
3. Verify:
   - The application does not crash.
   - A warning is logged: *"Speech recognition or PyAudio not installed — voice input disabled."*
   - Clicking the mic button shows a descriptive error banner in the GUI instead of crashing the process.

### 3.3 Max Tool Iterations (Anti-Looping)
- Force a tool to return a value that prompts the LLM to call it again.
- Verify that the orchestrator terminates the loop at exactly `MAX_ITERATIONS = 5` and returns: *"I've completed the available actions."* to prevent resource hogging.

---

## 4. Known Limitations

Documented design choices and backend limitations in Version 1.

| Component | Limitation / Behavior | Impact | Suggested V2 Fix |
|:---|:---|:---|:---|
| **Text-to-Speech (TTS)** | Pyttsx3's `runAndWait()` is a blocking synchronous call on the worker thread. The `stop()` call sets an event flag but cannot abort the speech synthesis mid-sentence. | The assistant cannot be interrupted mid-sentence; the user must wait for it to finish speaking. | Move to asynchronous TTS engine API or chunk text into small phrases and check stop flags between phrase dispatches. |
| **Speech-to-Text (STT)** | `recognizer.listen()` blocks the thread waiting for audio. Clicking "Stop Listening" sets `self._cancelled = True` but the thread remains blocked until silence is detected or timeout expires. | Delayed mic release when canceling recording manually. | Implement raw audio chunk streaming with an active cancel flag checking during buffer collection. |
| **Offline Mode** | Uses hardcoded keyword matching dictionary in `_offline_dispatch()`. | Strictly matches set phrases. Variations like "run notepad" instead of "open notepad" will fail. | Integrate a lightweight local regex parsing engine or a small, lightweight offline NLP classifier (e.g., SpaCy/NLTK). |
| **Knowledge Base (RAG)** | Utilizes standard SQLite `LIKE %query%` keyword SQL matching for chunk search. | No semantic understanding of queries (e.g., searching "automobile" won't match "car"). | Upgrade database storage to include a vector extension (e.g., `sqlite-vss` or ChromaDB) with local embeddings. |
| **RAG Instance Sharing** | Global module-level `_rag_instance` is initialized on startup by the controller. | Potential conflict if multiple controllers are initialized in tests. | Pass the `RAGService` instance directly into tool constructor factory instead of a global module variable. |
