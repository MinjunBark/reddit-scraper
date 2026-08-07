#!/usr/bin/env bash
# Run the Reddit intent-signal pipeline from any terminal.
#
#   ./run.sh                 real run — posts the digest to Discord, records what it sent
#   ./run.sh --dry-run       prints the digest, posts nothing, writes no state
#   ./run.sh --limit 10      cap total results (the cost lever)
#
# Any flags given are passed straight through to main.py.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ ! -x .venv/bin/python ]]; then
    echo "No virtualenv found. Creating one and installing dependencies..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
fi

if [[ ! -f .env ]]; then
    echo "ERROR: .env not found."
    echo "Run: cp .env.example .env   then fill in APIFY_TOKEN, GEMINI_API_KEY, DISCORD_WEBHOOK_URL"
    exit 1
fi

exec .venv/bin/python main.py "$@"
