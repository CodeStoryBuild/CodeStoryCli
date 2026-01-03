# vibe

**vibe** is a smart CLI wrapper around Git, designed to let developers focus on vibecoding while it handles the rest.  
It analyzes your diffs, groups changes into meaningful commits, and generates descriptive commit messages using local or remote LLMs.  
Beyond commits, vibe can help manage branches, PRs, protected branches, and linters — so your workflow stays smooth.

---

## ✨ Features

- 🔍 **Smart commit grouping** — break large diffs into smaller, focused commits.  
- 📝 **AI-generated commit messages** — powered by LLMs (Ollama, llama.cpp, OpenAI, etc.).  
- 🌱 **Branch & PR management** — automatic branch naming, PR creation, and rules for protected branches.  
- ✅ **DevOps integration** — linters, hooks, and workflows handled automatically.  
- ⚡ **Pluggable AI backends** — choose local (Ollama/llama.cpp) or online endpoints.  

## 🚀 Installation

### Using pip
```bash
pip install vibe
```

### Using pre-built executables
Download the latest executable for your platform from the [Releases](https://github.com/Ademfcan/vibecommit/releases) page.

## 🔨 Building from Source

### Building the executable
```bash
# Clone the repository
git clone https://github.com/Ademfcan/vibecommit.git
cd vibecommit

# Install dependencies
pip install -e .

# Build executable
python build_exe.py
# Or on Windows:
./build_exe.ps1
```

The executable will be available in the `dist` directory.
