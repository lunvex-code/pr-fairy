# ✨ PR Fairy

**A night fairy who fixes your repository while you sleep.**

[![Install PR Fairy](https://img.shields.io/badge/Install_with_one_command-FF69B4?style=for-the-badge&logo=terminal)](https://get.prfairy.dev)

> Your personal AI coding assistant that quietly improves your code at night.

---

## 🚀 One-Command Installation

The fastest way to get started:

```bash
curl -fsSL https://get.prfairy.dev | bash
```

Or directly from the repository:

```bash
curl -fsSL https://raw.githubusercontent.com/lunvex-code/pr-fairy/main/install.sh | bash
```

---

## 🌟 What Happens During Installation

PR Fairy guides you through a beautiful interactive setup:

1. **Welcome** – Quick confirmation to begin setup
2. **Language Selection** – Choose your preferred language (default: **English**)
3. **Ollama Check** – Automatically detects and helps install Ollama if needed
4. **Smart Model Selection** – Choose between:
   - Download the recommended model for intelligent fixes (`qwen2.5-coder:7b` recommended)
   - Pick from already installed Ollama models
   - Skip for now

After setup, you’ll see a success screen with your chosen language and model.

---

## 🧠 Smart LLM Mode

PR Fairy shines when using the `--llm` flag. It uses a local model to find **tiny, safe, high-quality improvements**:

- Real typos in documentation and comments
- Small readability improvements
- Obvious cleanups

The system is deliberately conservative — it only suggests changes it is highly confident about.

```bash
# Run with intelligent AI suggestions
fairy watch --llm

# Fully automatic mode (creates PRs for safe fixes)
fairy watch --auto --llm
```

---

## 📦 Main Commands

| Command                        | Description                                      |
|--------------------------------|--------------------------------------------------|
| `fairy install`                | Run the interactive setup wizard                 |
| `fairy watch`                  | Scan repositories for small safe fixes           |
| `fairy watch --llm`            | Use the local AI model for smarter suggestions   |
| `fairy watch --auto`           | Automatically create branches & commits          |
| `fairy watch --auto --llm`     | Full automatic mode with AI suggestions          |
| `fairy llm-test <file>`        | Debug / test what the model suggests for a file  |
| `fairy models`                 | List recommended and installed models            |
| `fairy config`                 | View or change settings (including language)     |

---

## 🛠 Requirements

- Python 3.10+
- Ollama (automatically installed during setup if missing)
- Git

PR Fairy works fully locally — your code never leaves your machine.

---

## 🌍 Language Support

During installation you can choose between **English** and **Русский**.

You can change the default language later:

```bash
fairy config language ru
# or
fairy config language en
```

---

## 🔧 Configuration

PR Fairy stores its settings in:

```
~/.config/pr-fairy/config.yaml
```

You can edit it manually or use the `fairy config` command.

---

## 💡 Philosophy

PR Fairy only makes **small, obviously correct** changes. It will never:

- Refactor logic
- Change function or variable names
- Touch business-critical code
- Make large or risky modifications

Its goal is to remove tiny amounts of tech debt while you sleep — the kind of fixes that are valuable but easy to forget.

---

## 🤝 Contributing

Contributions are welcome! Please run:

```bash
fairy install
```

...and help us improve the experience.

---

## 📜 License

MIT © PR Fairy Team

---

**Made with care for developers who value clean, quiet improvements.** 🌙
