# License Rationale & Compliance

## 1. Recommendation: MIT License with GPLv3 Compliance Notice

We recommend releasing **Futurix Jarvis** source code under the **MIT License**. This choice encourages community adoption, developer contribution, and simple integration. However, because the user interface is built using **PyQt6**, there are specific compliance rules that developers and users must follow.

---

## 2. PyQt6 License Constraints (GPLv3)

PyQt6 is developed by Riverbank Computing and is dual-licensed:
1. **GNU General Public License v3 (GPLv3)**: Free for open-source applications.
2. **Commercial License**: Required if you wish to distribute closed-source commercial applications.

### **Compliance Rules for Futurix Jarvis**
- **Source Code**: You are free to license the core, non-GUI code files (e.g. LLM routing, RAG services, database management) under the permissive **MIT License**.
- **Binaries & Bundles**: If you compile this project into a standalone executable (e.g. via PyInstaller) that bundles PyQt6 and distribute it to third parties, the entire combined work **must** be distributed under the terms of the **GPLv3 License** (or you must buy a commercial license from Riverbank Computing).
- **Public Repository**: To avoid any ambiguity, this project includes this compliance disclaimer alongside the standard MIT License.

---

## 3. MIT License Text

```text
MIT License

Copyright (c) 2026 Futurix

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
