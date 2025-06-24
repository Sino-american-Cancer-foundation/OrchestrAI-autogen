#!/bin/bash

# Determine the absolute path to this script's directory
FORMAT_PROXY_ARCHITECTURE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

# Determine absolute path to Python directory (two levels up from this script's location)
PYTHON_DIR=$(cd "$FORMAT_PROXY_ARCHITECTURE_DIR/../.." &>/dev/null && pwd)

# Determine absolute path to Project Root directory (one level up from Python directory)
PROJECT_ROOT_DIR=$(cd "$PYTHON_DIR/.." &>/dev/null && pwd)

# Absolute path to venv activate script and python interpreter
VENV_ACTIVATE="$PYTHON_DIR/.venv/bin/activate"
PYTHON_INTERPRETER="$PYTHON_DIR/.venv/bin/python"

SESSION_NAME="format_proxy_architecture"

# Kill existing session if any, to ensure a clean start
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# Start a new tmux session, with CWD set to PROJECT_ROOT_DIR
tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_ROOT_DIR"

# Split the terminal into panes as per the user's example structure
tmux split-window -h -t "$SESSION_NAME:0.0"
tmux select-pane -t "$SESSION_NAME:0.0"
tmux split-window -v -t "$SESSION_NAME:0.0"
tmux select-pane -t "$SESSION_NAME:0.1"
tmux split-window -v -t "$SESSION_NAME:0.1"
tmux select-pane -t "$SESSION_NAME:0.0"
tmux split-window -v -t "$SESSION_NAME:0.0"

# Select the first pane (target for the first command, though not strictly necessary as we target panes explicitly)
tmux select-pane -t "$SESSION_NAME:0.0"

# Run the scripts in each pane
# Commands are run with $PYTHON_DIR as CWD due to '-c "$PYTHON_DIR"' in new-session.

# Pane 0.0: Host
# Runs under python/
CMD_HOST="cd '$PYTHON_DIR' && source '$VENV_ACTIVATE' && '$PYTHON_INTERPRETER' -m samples.format_proxy_architecture.run_host"
tmux send-keys -t "$SESSION_NAME:0.0" "$CMD_HOST" C-m

# Pane 0.1: UI
# Runs under project root/
CMD_UI="source '$VENV_ACTIVATE' && cd '$PROJECT_ROOT_DIR' && PYTHONPATH=$PYTHONPATH:$(pwd)/python chainlit run python/samples/format_proxy_architecture/run_ui.py --port 8001"
tmux send-keys -t "$SESSION_NAME:0.1" "$CMD_UI" C-m

# Pane 0.2: Format Proxy
# Runs under python/
CMD_FP="cd '$PYTHON_DIR' && source '$VENV_ACTIVATE' && '$PYTHON_INTERPRETER' -m samples.format_proxy_architecture.run_format_proxy"
tmux send-keys -t "$SESSION_NAME:0.2" "$CMD_FP" C-m

# Pane 0.3: Domain Agent
# Runs under python/
CMD_DA="cd '$PYTHON_DIR' && source '$VENV_ACTIVATE' && '$PYTHON_INTERPRETER' -m samples.format_proxy_architecture.run_domain_agent"
tmux send-keys -t "$SESSION_NAME:0.3" "$CMD_DA" C-m

# Pane 0.4: Orchestrator
# Runs under python/
CMD_ORCH="cd '$PYTHON_DIR' && source '$VENV_ACTIVATE' && '$PYTHON_INTERPRETER' -m samples.format_proxy_architecture.run_orchestrator"
tmux send-keys -t "$SESSION_NAME:0.4" "$CMD_ORCH" C-m

# Attach to the session
tmux attach-session -t "$SESSION_NAME" 