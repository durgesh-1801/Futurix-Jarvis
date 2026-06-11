# Futurix Jarvis — Version 2.0 Implementation Plan

This document details the file-level changes, milestones, testing protocols, and safety rollback strategies for implementing the Version 2.0 upgrades.

---

## 1. File Changes Matrix

### 1.1 New Files to Be Created
| Path | Purpose | Est. Lines |
|:---|:---|:---|
| [knowledge/vector_store_interface.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/knowledge/vector_store_interface.py) | Abstract base class `VectorStoreInterface`. | ~30 |
| [knowledge/chroma_store.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/knowledge/chroma_store.py) | Concrete ChromaDB vector store client. | ~80 |
| [vision/vision_provider.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/vision/vision_provider.py) | `VisionProviderInterface` and `OllamaVisionProvider`. | ~90 |
| [vision/vision_service.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/vision/vision_service.py) | Core Vision tools (`analyse_screenshot`, etc.). | ~80 |
| [coding/workspace_index.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/coding/workspace_index.py) | AST workspace indexer and repository summary logic. | ~180 |
| `tests/test_voice.py` | Unit tests for voice streaming and interruption. | ~100 |

### 1.2 Existing Files to Be Modified
| Path | Modifications | Est. Lines (Change) |
|:---|:---|:---|
| [voice/text_to_speech.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/voice/text_to_speech.py) | Implement word callbacks and SAPI5 interrupt handlers. | +45 |
| [voice/speech_to_text.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/voice/speech_to_text.py) | Refactor `listen` loop to read micro-buffers from PyAudio stream directly. | +60 |
| [database/db_manager.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/database/db_manager.py) | Add `repository_summary`, `tasks`, and `code_symbols` database tables. | +90 |
| [knowledge/rag_service.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/knowledge/rag_service.py) | Connect to `VectorStoreInterface` and use local embeddings. | -40 / +70 |
| [coding/coding_agent.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/coding/coding_agent.py) | Add AST and metadata querying tools; integrate compiler syntax check. | +80 |
| [gui/chat_widget.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/gui/chat_widget.py) | Render interactive confirmation message blocks (Approve/Reject/Always Allow). | +85 |
| [assistant/controller.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/assistant/controller.py) | Set up vision provider, thread execution blocks, and dynamic query routing. | +90 |
| [assistant/agent.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/assistant/agent.py) | Integrate RoutingService and Vision tools. | +50 |
| [config/settings.py](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/config/settings.py) | Expose model paths and validation fields. | +20 |
| [requirements.txt](file:///C:/Users/user/.gemini/antigravity-ide/scratch/futurix_jarvis/requirements.txt) | Add ChromaDB and Pydantic. | +5 |

---

## 2. Milestone Breakdown

```
Milestone 1 (Voice Interrupts)    ---> Milestone 2 (Semantic RAG & Interfaces)
          [CURRENT]
                 |
                 v
Milestone 3 (Multi-Model Router)  ---> Milestone 4 (Interactive UI Confirmations)
                 |
                 v
Milestone 5 (Vision & AST Coding) ---> Verification & Release
```

- **Milestone 1: Voice Interruption (Phase 1)**
  - Implement word-event listeners in TTS and incremental mic streams in STT.
  - Deliver instant stop responses. Validate with unit tests.
- **Milestone 2: Vector Store Abstractions & Chroma RAG (Phase 2)**
  - Implement `VectorStoreInterface` and ChromaDB vector store integration.
  - Implement Ollama embeddings query pipeline.
- **Milestone 3: Modular Query Router (Phase 3)**
  - Deploy `RoutingService` executing rule-based models routing.
  - Test routing logs output.
- **Milestone 4: Interactive Confirmations with DB Logs (Phase 4)**
  - Integrate inline message-bubble confirmation cards with threading lock release.
  - Verify SQLite audit trail logs.
- **Milestone 5: Vision Provider & AST Indexer (Phase 5)**
  - Expose `VisionProviderInterface` with `OllamaVisionProvider` (LLaVA model).
  - Deploy workspace AST parser mapping symbols to SQLite records.

---

## 3. Testing Strategy

1.  **Unit Tests**: Run tests via `pytest` focusing on the thread state control of background workers.
    *   TTS: Assert that calling `stop()` terminates output stream mid-sentence.
    *   STT: Assert that setting `_is_cancelled` terminates mic stream in < 100ms.
2.  **Mocking I/O**: Mock PyAudio sound streams and `pyttsx3` driver states where sound cards are unavailable.
3.  **Manual Verification checklist**: Check voice interruption responsiveness using keyboard interrupts and clicking the GUI mic button.

---

## 4. Rollback Strategy

1.  **Git Branching**: Develop V2 changes on isolated topic branches (`feature/v2-voice`, `feature/v2-rag`).
2.  **Database Fail-safe**: Before altering database schema, copy `data/jarvis.db` to a backup location `data/jarvis.db.bak`.
3.  **Graceful Degrades**:
    *   If ChromaDB encounters a dynamic library mismatch on Windows, fallback automatically to the memory-based storage engine or SQL keyword `LIKE` query engine.
    *   If routed LLM models are missing from the local server, default immediately to the configured `ollama_model` fallback parameter.
