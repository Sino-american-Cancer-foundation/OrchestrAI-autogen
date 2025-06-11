#!/bin/bash

# Determine the absolute path to this script's directory (samples/)
SAMPLES_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

# Determine absolute path to insurance-eligibility-check directory (parent of samples)
INSURANCE_CHECK_DIR=$(cd "$SAMPLES_DIR/.." &>/dev/null && pwd)

# Determine absolute path to core_proxy_agent_example directory (parent of insurance-eligibility-check)
PROXY_AGENT_DIR=$(cd "$INSURANCE_CHECK_DIR/.." &>/dev/null && pwd)

# Determine absolute path to Python directory (two levels up from proxy agent directory)
PYTHON_DIR=$(cd "$PROXY_AGENT_DIR/../.." &>/dev/null && pwd)

# Determine absolute path to Project Root directory (one level up from Python directory)
PROJECT_ROOT_DIR=$(cd "$PYTHON_DIR/.." &>/dev/null && pwd)

# Absolute path to venv activate script and python interpreter
VENV_ACTIVATE="$PYTHON_DIR/.venv/bin/activate"
PYTHON_INTERPRETER="$PYTHON_DIR/.venv/bin/python"

SESSION_NAME="insurance_eligibility_check"

# Kill existing session if any, to ensure a clean start
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# Start a new tmux session, with CWD set to SAMPLES_DIR
# This makes it easier to run the sample scripts directly
tmux new-session -d -s "$SESSION_NAME" -c "$SAMPLES_DIR"

# Split into 5 panes for our 5 components
# First split horizontally to create 2 columns
tmux split-window -h -t "$SESSION_NAME:0.0"

# Split left column into 3 panes (Host, Proxy, Medical Data)
tmux split-window -v -t "$SESSION_NAME:0.0"
tmux split-window -v -t "$SESSION_NAME:0.1"

# Split right column into 2 panes (UI, Orchestrator)
tmux split-window -v -t "$SESSION_NAME:0.3"

# Define commands for each pane
# Set PYTHONPATH to include the insurance-eligibility-check directory
# so that "import insurance_eligibility_check" works correctly
PYTHONPATH_DIR="$INSURANCE_CHECK_DIR"

# Pane 0: Host
CMD_HOST="source '$VENV_ACTIVATE' && cd '$SAMPLES_DIR' && export PYTHONPATH='$PYTHONPATH_DIR' && '$PYTHON_INTERPRETER' run_host.py"
tmux send-keys -t "$SESSION_NAME:0.0" "$CMD_HOST" C-m

# Small delay for host to start
sleep 2

# Pane 1: Proxy Agent
CMD_PROXY="source '$VENV_ACTIVATE' && cd '$SAMPLES_DIR' && export PYTHONPATH='$PYTHONPATH_DIR' && '$PYTHON_INTERPRETER' run_proxy_agent.py"
tmux send-keys -t "$SESSION_NAME:0.1" "$CMD_PROXY" C-m

# Pane 2: Medical Data Agent
CMD_MEDICAL="source '$VENV_ACTIVATE' && cd '$SAMPLES_DIR' && export PYTHONPATH='$PYTHONPATH_DIR' && '$PYTHON_INTERPRETER' run_medical_data_agent.py"
tmux send-keys -t "$SESSION_NAME:0.2" "$CMD_MEDICAL" C-m

# Pane 3: UI (Chainlit)
CMD_UI="source '$VENV_ACTIVATE' && cd '$SAMPLES_DIR' && export PYTHONPATH='$PYTHONPATH_DIR' && chainlit run run_ui.py --port 8001"
tmux send-keys -t "$SESSION_NAME:0.3" "$CMD_UI" C-m

# Small delay for UI to start
sleep 2

# Pane 4: Orchestrator Agent
CMD_ORCHESTRATOR="source '$VENV_ACTIVATE' && cd '$SAMPLES_DIR' && export PYTHONPATH='$PYTHONPATH_DIR' && '$PYTHON_INTERPRETER' run_orchestrator_agent.py"
tmux send-keys -t "$SESSION_NAME:0.4" "$CMD_ORCHESTRATOR" C-m

echo "🏥 Insurance Eligibility Check System Starting..."
echo "📁 Working from: $SAMPLES_DIR"
echo "🐍 PYTHONPATH: $PYTHONPATH_DIR"
echo "💡 UI will be available at: http://localhost:8001"
echo ""
echo "🔄 Use Ctrl+B then D to detach from tmux session"
echo "🔄 Use 'tmux attach -t $SESSION_NAME' to reattach"

# Attach to the session
tmux attach-session -t "$SESSION_NAME" 