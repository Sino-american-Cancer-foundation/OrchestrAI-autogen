#!/bin/bash

# Determine the absolute path to this script's directory
WRAPPER_AGENT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

# Determine absolute path to Python directory (two levels up from this script's location)
PYTHON_DIR=$(cd "$WRAPPER_AGENT_DIR/../.." &>/dev/null && pwd)

# Determine absolute path to Project Root directory (one level up from Python directory)
PROJECT_ROOT_DIR=$(cd "$PYTHON_DIR/.." &>/dev/null && pwd)

# Absolute path to venv activate script and python interpreter
VENV_ACTIVATE="$PYTHON_DIR/.venv/bin/activate"
PYTHON_INTERPRETER="$PYTHON_DIR/.venv/bin/python"

SESSION_NAME="wrapper_agent_example"

# Kill existing session if any, to ensure a clean start
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# Start a new tmux session, with CWD set to PROJECT_ROOT_DIR
# This makes paths relative to the project root easier to manage.
tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_ROOT_DIR"

# Split into 3 panes horizontally
tmux split-window -h -t "$SESSION_NAME:0.0"
tmux split-window -h -t "$SESSION_NAME:0.1"

# Select the first pane (optional, as we target panes explicitly)
tmux select-pane -t "$SESSION_NAME:0.0"

# Define commands for each pane
# Common parts: activate venv, set PYTHONPATH to $PYTHON_DIR
# $PYTHON_DIR is the directory containing the 'samples' package (e.g., .../OrchestrAI-autogen/python)

# Pane 0: Host
# Runs 'run_host.py' as a module from PROJECT_ROOT_DIR
CMD_HOST="source '$VENV_ACTIVATE' && export PYTHONPATH='$PYTHON_DIR' && '$PYTHON_INTERPRETER' -m samples.wrapper_agent_example.run_host"
tmux send-keys -t "$SESSION_NAME:0.0" "$CMD_HOST" C-m

# Pane 1: UI (Chainlit)
# Runs 'run_ui.py' using chainlit, path to script is relative to PROJECT_ROOT_DIR
CMD_UI="source '$VENV_ACTIVATE' && export PYTHONPATH='$PYTHON_DIR' && chainlit run python/samples/wrapper_agent_example/run_ui.py --port 8002"
tmux send-keys -t "$SESSION_NAME:0.1" "$CMD_UI" C-m

# Pane 2: Wrapper Agent
# Runs 'run_wrapper_agent.py' as a module from PROJECT_ROOT_DIR
CMD_WRAPPER="source '$VENV_ACTIVATE' && export PYTHONPATH='$PYTHON_DIR' && '$PYTHON_INTERPRETER' -m samples.wrapper_agent_example.run_wrapper_agent"
tmux send-keys -t "$SESSION_NAME:0.2" "$CMD_WRAPPER" C-m

# Attach to the session
tmux attach-session -t "$SESSION_NAME" 