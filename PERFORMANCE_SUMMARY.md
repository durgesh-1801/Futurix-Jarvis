# Performance Summary

This document tabulates the benchmarked execution speeds and performance characteristics of core subsystems in Futurix Jarvis, based on the June 11, 2026 validation pass.

---

## 1. Subsystem Execution Speeds

The following table summarizes the time taken by each system component under test:

| Subsystem Task | Execution Speed / Latency | Description |
| :--- | :--- | :--- |
| **Intent Pattern Routing** | `< 1.0 ms` | Regular expression string cleaning, punctuation stripping, and matching against intent mappings. |
| **Screen Capture** | `~340 ms to 380 ms` | Capturing the desktop display buffer and writing a PNG payload to disk. |
| **Workspace Indexing** | `~10.74 seconds` | AST-parsing 75 python files (11,870 lines of code) and extracting 962 symbols into SQLite. (Average: ~143ms per file) |
| **Direct Tool Execution (get_battery_status)** | `< 5.0 ms` | Querying the physical battery details via Windows kernel (`GetSystemPowerStatus`). |
| **Direct Tool Execution (get_resource_usage)** | `~1,000 ms` | Compiles CPU utilization over a 1-second sample interval using `psutil.cpu_percent(interval=1)`. |
| **ReAct Loop Fallback Overhead** | `~1,200 ms` | Core system framework overhead per ReAct prompt generation (excluding Ollama local inference delay). |

---

## 2. Resource Footprint Metrics

The following metrics show baseline and stress metrics during a 30+ mixed-command session:

*   **Baseline Idle Memory**: 69.10 MB (RSS)
*   **Active Processing Memory**: 75.02 MB (RSS)
*   **Thread Count Baseline**: 1 active thread
*   **Thread Count Active (Worker Runs)**: 2 active threads (1 GUI main thread + 1 background worker thread)
*   **Disk Indexing Payload Size**: `jarvis.db` expands by approximately ~180 KB post codebase indexing.
