#!/bin/bash
# Start a new tmux session
tmux new-session -d -s format_proxy_architecture

# Split the terminal into panes
tmux split-window -h
tmux select-pane -t format_proxy_architecture:0.0
tmux split-window -v
tmux select-pane -t format_proxy_architecture:0.1
tmux split-window -v
tmux select-pane -t format_proxy_architecture:0.0
tmux split-window -v

# Select the first pane
tmux select-pane -t format_proxy_architecture:0.0

# Run the scripts in each pane with venv activation
tmux send-keys -t format_proxy_architecture:0.0 "source .venv/bin/activate && python samples/format_proxy_architecture/run_host.py" C-m
tmux send-keys -t format_proxy_architecture:0.1 "source .venv/bin/activate && chainlit run samples/format_proxy_architecture/run_ui.py --port 8001" C-m
tmux send-keys -t format_proxy_architecture:0.2 "source .venv/bin/activate && python samples/format_proxy_architecture/run_format_proxy.py" C-m
tmux send-keys -t format_proxy_architecture:0.3 "source .venv/bin/activate && python samples/format_proxy_architecture/run_domain_agent.py" C-m
tmux send-keys -t format_proxy_architecture:0.4 "source .venv/bin/activate && python samples/format_proxy_architecture/run_orchestrator.py" C-m

# Attach to the session
tmux attach-session -t format_proxy_architecture
