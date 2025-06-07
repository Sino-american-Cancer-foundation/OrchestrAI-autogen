#!/bin/bash

# Determine the absolute path to this script's directory
PROXY_AGENT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

# Determine absolute path to Python directory (two levels up from this script's location)
PYTHON_DIR=$(cd "$PROXY_AGENT_DIR/../.." &>/dev/null && pwd)

# Determine absolute path to Project Root directory (one level up from Python directory)
PROJECT_ROOT_DIR=$(cd "$PYTHON_DIR/.." &>/dev/null && pwd)

# Absolute path to venv activate script and python interpreter
VENV_ACTIVATE="$PYTHON_DIR/.venv/bin/activate"
PYTHON_INTERPRETER="$PYTHON_DIR/.venv/bin/python"

SESSION_NAME="core_proxy_agent_example"

# Kill existing session if any, to ensure a clean start
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# Start a new tmux session, with CWD set to PROJECT_ROOT_DIR
# This makes paths relative to the project root easier to manage.
tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_ROOT_DIR"

# Split into 5 panes for our 5 components
# First split horizontally to create 2 columns
tmux split-window -h -t "$SESSION_NAME:0.0"

# Split left column into 3 panes (Host, Proxy, Medical Data)
tmux split-window -v -t "$SESSION_NAME:0.0"
tmux split-window -v -t "$SESSION_NAME:0.1"

# Split right column into 2 panes (UI, Orchestrator)
tmux split-window -v -t "$SESSION_NAME:0.3"

# Define commands for each pane
# Common parts: activate venv, set PYTHONPATH to $PYTHON_DIR
# $PYTHON_DIR is the directory containing the 'samples' package

# Pane 0: Host
CMD_HOST="source '$VENV_ACTIVATE' && export PYTHONPATH='$PYTHON_DIR' && '$PYTHON_INTERPRETER' -m samples.core_proxy_agent_example.run_host"
tmux send-keys -t "$SESSION_NAME:0.0" "$CMD_HOST" C-m

# Small delay for host to start
sleep 2

# Pane 1: Proxy Agent
CMD_PROXY="source '$VENV_ACTIVATE' && export PYTHONPATH='$PYTHON_DIR' && '$PYTHON_INTERPRETER' -m samples.core_proxy_agent_example.run_proxy_agent"
tmux send-keys -t "$SESSION_NAME:0.1" "$CMD_PROXY" C-m

# Pane 2: Medical Data Agent
CMD_MEDICAL="source '$VENV_ACTIVATE' && export PYTHONPATH='$PYTHON_DIR' && '$PYTHON_INTERPRETER' -m samples.core_proxy_agent_example.run_medical_data_agent"
tmux send-keys -t "$SESSION_NAME:0.2" "$CMD_MEDICAL" C-m

# Pane 3: UI (Chainlit)
CMD_UI="source '$VENV_ACTIVATE' && export PYTHONPATH='$PYTHON_DIR' && chainlit run python/samples/core_proxy_agent_example/run_ui.py --port 8001"
tmux send-keys -t "$SESSION_NAME:0.3" "$CMD_UI" C-m

# Small delay for UI to start
sleep 2

# Pane 4: Orchestrator Agent
CMD_ORCHESTRATOR="source '$VENV_ACTIVATE' && export PYTHONPATH='$PYTHON_DIR' && '$PYTHON_INTERPRETER' -m samples.core_proxy_agent_example.run_orchestrator_agent"
tmux send-keys -t "$SESSION_NAME:0.4" "$CMD_ORCHESTRATOR" C-m

# Attach to the session
tmux attach-session -t "$SESSION_NAME" 