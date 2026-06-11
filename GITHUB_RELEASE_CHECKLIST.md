# GitHub Release Checklist — Futurix Jarvis

This document outlines the step-by-step checklist required to prepare **Futurix Jarvis** for a production-ready GitHub release, covering file cleanups, media assets, tagging schemes, and open-source readiness.

---

## Phase 1: Repository Cleanup & Safety Audit
- [ ] **Verify `.gitignore` Coverage**: Ensure no sensitive files, personal configs, or database instances are tracked in git.
  - Check that `.env`, `data/jarvis.db`, `data/chroma_db/`, `logs/`, `*.spec`, `dist/`, `build/`, and `.venv/` are excluded.
- [ ] **Purge Temporary Artifacts**: Remove local experiment files, test outputs, and compiler caches before committing:
  ```cmd
  git clean -fdX --dry-run
  ```
- [ ] **Verify `.env.example` completeness**: Ensure all default environment variables are documented with placeholder values (e.g. database path, model names, base URLs) without exposing any private configurations.

---

## Phase 2: Complete Test Suite & Fallback Verification
- [ ] **Run Core Unit Tests**: Verify 100% test pass status in a clean environment:
  ```cmd
  .venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
  ```
- [ ] **Execute RAG and Vision Benchmarks**: Verify that embedding ingestion and screenshot OCR perform within expected latencies (<1.5s).
- [ ] **Verify Offline/Fallback Capabilities**:
  - [ ] Terminate local Ollama and run Jarvis. Verify that it starts up successfully and functions via fallback regular expressions.
  - [ ] Block ChromaDB initialization (simulate old sqlite dll) and verify that the app seamlessly uses the `InMemoryVectorStore` TF-IDF indexing.

---

## Phase 3: Visual & Demo Asset Preparation
- [ ] **Capture Example Screenshots**: Save high-quality PNG screenshots of the following states in the `assets/` directory:
  - **Main GUI Panel**: Showing a sample chat history, glowing neon styling, and sidebar history.
  - **Inline Approval Dialog**: Showing a command execution request (e.g. launching Notepad) waiting for user "Approve/Reject" input.
  - **Task Memory Widget**: Displaying prioritized task checklists (Low/Medium/High) with due dates.
- [ ] **Record Demo GIF / Video**: Create a 30–60 second silent demo video (or high-framerate GIF) showing:
  1. The user typing *"Open Calculator"* and approving the popup.
  2. The user asking a semantic question about a recently ingested PDF.
  3. The voice-activation stream reacting to audio input.
- [ ] **Update README.md**: Embed the captured screenshots and GIF at the top of the `README.md` to wow visitors immediately.

---

## Phase 4: Build & Packaging Assets
- [ ] **Generate PyInstaller Executable**: Compile the application into a standalone folder using the Windows spec:
  ```cmd
  pyinstaller --noconfirm --onedir --windowed --name="FuturixJarvis" --clean main.py
  ```
- [ ] **Verify Executable Startup**: Test the built executable (`dist/FuturixJarvis/FuturixJarvis.exe`) on a clean Windows machine without python installed to verify all DLLs, resources, and SQLite setups migrate properly.
- [ ] **Create Installer Package**: Zip the compiled folder into a file named `futurix-jarvis-v2.0.0-windows-x64.zip` for release download attachment.

---

## Phase 5: Git Tagging & Release Publishing
- [ ] **Commit Version Bump**: Set version in `main.py` (or metadata) to `2.0.0`.
- [ ] **Create Git Tag**: Tag the commit using Semantic Versioning (vX.Y.Z) and push to GitHub:
  ```cmd
  git tag -a v2.0.0 -m "Release v2.0.0"
  git push origin v2.0.0
  ```
- [ ] **Draft GitHub Release Draft**:
  - **Title**: `v2.0.0 - Semantic RAG, Vision Diagnostics, and Voice Automation`
  - **Release Notes**: Copy highlights from the walkthrough, include system requirements, model commands, and attach the pre-built `futurix-jarvis-v2.0.0-windows-x64.zip`.
  - **Publish**: Check as "Latest Release".
