# Contributing to Futurix Jarvis

First off, thank you for taking the time to contribute! We welcome contributions from developers of all skill levels. By participating in this project, you help make **Futurix Jarvis** a more stable, secure, and feature-rich assistant.

---

## 1. Coding Standards & Style

To maintain code quality and readability, please adhere to these guidelines:
- **Style Guide**: Follow **PEP 8** coding standards for Python.
- **Type Hints**: Use type annotations for all function parameters and return types (e.g., `def query_model(self, prompt: str) -> dict:`).
- **Docstrings**: Provide Google-style docstrings for all classes, methods, and functions:
  ```python
  def get_symbols(self, file_path: str) -> list[dict]:
      """Parses a Python file and extracts AST symbols.

      Args:
          file_path: The absolute path to the Python source file.

      Returns:
          A list of symbol metadata dictionaries.
      """
  ```
- **Error Handling**: Use specific exception catches rather than bare `except:`. Ensure that background worker threads pass exceptions back to the main UI thread via PyQt signals instead of raising unhandled thread crashes.

---

## 2. Setting Up Your Development Environment

1. **Fork the Repository**: Create a fork of the project on GitHub.
2. **Clone Locally**:
   ```cmd
   git clone https://github.com/your-username/futurix_jarvis.git
   cd futurix_jarvis
   ```
3. **Setup Virtual Environment**:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```
4. **Install Dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```
5. **Start Ollama Locally**: Make sure you have Ollama running and the required models pulled:
   ```cmd
   ollama serve
   ollama pull llama3
   ollama pull nomic-embed-text
   ollama pull llava
   ```

---

## 3. Running the Test Suite

Before submitting any code changes, ensure all tests pass:
- **Run Functional & Unit Tests**:
  ```cmd
  .venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
  ```
- **Run Benchmarks** (to ensure no performance regressions):
  ```cmd
  .venv\Scripts\python.exe tests/benchmark_phase2.py
  .venv\Scripts\python.exe tests/benchmark_phase3.py
  ```

---

## 4. Submitting a Pull Request (PR)

1. **Branch Naming**: Create a descriptive branch name:
   - For bug fixes: `bugfix/issue-description`
   - For features: `feature/feature-name`
   - For documentation: `docs/update-title`
2. **Keep Commits Clean**: Use clear, concise commit messages (e.g., `feat: integrate nomic-embed-text fallback vector store`).
3. **Validate Your Changes**: Test your modifications locally (both manual UI operations and the unittest suite).
4. **Submit PR**: Open a PR against the `main` branch. Provide a detailed summary of your changes, any modifications made to database schemas, and verification screenshots if you modified the PyQt6 GUI.
