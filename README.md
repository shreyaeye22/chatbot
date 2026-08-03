# chatbot
my own chatbot for school

## Setup

This project uses [uv](https://github.com/astral-sh/uv) to manage the Python version, virtual environment, and dependencies.

1. Install uv (Windows): `winget install --id=astral-sh.uv -e`
2. Install the project's Python version and create the venv: `uv sync`
3. Run the app: `uv run main.py`

No manual venv activation is required — `uv run` uses `.venv` automatically. To activate it in your shell anyway: `.venv\Scripts\activate` (PowerShell/cmd) or `source .venv/Scripts/activate` (Git Bash).
