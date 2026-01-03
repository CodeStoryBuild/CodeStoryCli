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

## 📦 CI/CD with GitHub Actions

This repository is configured with GitHub Actions to automatically build executables for Windows, macOS, and Linux whenever code is pushed to a branch containing "release" in its name.

### Release Process:
1. Create and push a branch with "release" in its name (e.g., `release/1.0.0`, `feature-release`)
2. The GitHub Action will automatically build executables for all platforms
3. A new release will be created with the executables attached

### Version Naming:
- If your branch name follows the pattern `release[-/]X.Y.Z` (e.g., `release/1.2.3`), the version will be extracted from the branch name
- Otherwise, a timestamp will be used as the version

AA
AA
AA
AA
AA
AA
AA
AA
AA
AA
AA
AA
AA
AA
AA

---