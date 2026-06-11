# Security Review — Futurix Jarvis

This document provides a security audit and threat model assessment for the desktop integration tools, file parsers, and local model query structures in **Futurix Jarvis**.

---

## 1. Threat Model & Audit Areas

### 1.1 Command Execution Safety
- **Risk**: The agent could execute destructive shell commands (e.g. `rmdir /s /q`) on behalf of a malicious prompt.
- **Safeguards**:
  - The `confirm_commands` flag in `config/settings.py` is enabled by default.
  - All command executions routed through `automation/system_commands.py` trigger an inline Qt dialogue card, halting thread execution until the user selects **Approve**.
  - System terminal operations are run through `subprocess.run` with explicit list arguments rather than `shell=True` to prevent shell injection.

### 1.2 File System Access Review
- **Risk**: Path traversal attacks allowing the agent to overwrite system files (e.g. `..\..\Windows\System32`).
- **Safeguards**:
  - File manager actions resolve paths using `.resolve()` and verify that the path belongs to the active project workspace.
  - Directory write permissions are restricted inside the sandboxed workspace folder.

### 1.3 Tool Permission Boundaries
- **Scope**: Jarvis divides tools into two permission levels:
  1. **Standard (Read-only / Safe)**: Web searches, system specifications, symbol lookups. Executed automatically.
  2. **Elevated (Destructive / Write)**: App terminating, file modifications, command lines. Triggers inline GUI validation warnings.

### 1.4 Prompt Injection Safeguards
- **Risk**: Indirect prompt injection where ingested source files or documents contain instructions like *"Delete all projects"*.
- **Mitigation**:
  - The system prompt enforces that the LLM operates strictly as a ReAct planner.
  - LLM instructions cannot bypass GUI-enforced inline validation widgets, which are run on the native PyQt thread outside the model's environment.

### 1.5 RAG Poisoning Scenarios
- **Risk**: Ingesting poisoned PDF or Markdown files that trick the retriever into prioritizing fake entries.
- **Mitigation**:
  - Text extraction is sanitised: pypdf reads raw text strings without executing macros, forms, or scripts.
  - Clean SQLite parameter binding (`?`) is used in `store_knowledge_chunk` to prevent SQL injection during chunk loading.

### 1.6 Vision Prompt Abuse Scenarios
- **Risk**: Screenshots containing visual prompts that tell the model to ignore user instructions and run shell scripts.
- **Mitigation**:
  - The vision service only returns the *text description* of the screen to the controller. The controller does not treat this description as code or commands to be executed directly, rendering text-to-action injections ineffective.

### 1.7 Dangerous Automation Review
- **Risk**: The agent could trigger runaway keyboard/mouse simulation loops (via pyautogui), kill system-critical processes (via psutil), or get stuck in infinite ReAct planning execution loops that consume host system resources.
- **Mitigation**:
  - **Process Blocklist**: Automation tools restrict process termination; key OS tasks (e.g. explorer.exe, system services, and Jarvis itself) are blocklisted from termination.
  - **Execution Loop Cap**: The ReAct orchestrator has a hardcoded maximum threshold of 8 tool execution loops. If the agent does not resolve a task in 8 steps, it self-terminates the sequence and prompts the user for clarification.
  - **PyAutoGUI Safeguard**: PyAutoGUI is configured with `FAILSAFE = True` by default. If the mouse is manually pushed to any of the 4 screen corners, all active automation operations immediately abort.

---

## 2. Security Assessment Summary

| Threat Vector | Severity | Safeguard Status | Residual Risk |
| :--- | :---: | :---: | :---: |
| **Shell Injections** | High | Resolved (List arguments, UI approvals) | Low |
| **Path Traversal** | High | Resolved (Workspace path resolution) | Low |
| **Prompt Injection** | Medium | Partially Mitigated (GUI approvals, System prompt locks) | Low |
| **SQL Injection** | Medium | Resolved (Parameter binding) | None |
| **Dangerous Automation** | Medium | Resolved (Max loops, process blocklist, failsafe active) | Low |
