#!/bin/bash
# Start a new tmux session named 'insurance_verification'
tmux new-session -d -s insurance_verification

# Split the terminal into panes
tmux split-window -h

# Split the left pane into panes
tmux select-pane -t insurance_verification:0.0
tmux split-window -v
tmux select-pane -t insurance_verification:0.0
tmux split-window -v

# Split the right pane horizontally
tmux select-pane -t insurance_verification:0.3
tmux split-window -v
tmux select-pane -t insurance_verification:0.3
tmux split-window -v
tmux select-pane -t insurance_verification:0.5
tmux split-window -v

# Select the first pane to start
tmux select-pane -t insurance_verification:0.0

# Activate the virtual environment and run the scripts in each pane
tmux send-keys -t insurance_verification:0.0 "python run_host.py" C-m
tmux send-keys -t insurance_verification:0.1 "chainlit run run_ui.py --port 8001" C-m
tmux send-keys -t insurance_verification:0.3 "python run_web_navigation_agent.py" C-m
tmux send-keys -t insurance_verification:0.4 "python run_image_analysis_agent.py" C-m
tmux send-keys -t insurance_verification:0.5 "python run_healthcare_task_agent.py" C-m
tmux send-keys -t insurance_verification:0.6 "python run_group_chat_manager.py" C-m

# Attach to the session
tmux attach-session -t insurance_verification