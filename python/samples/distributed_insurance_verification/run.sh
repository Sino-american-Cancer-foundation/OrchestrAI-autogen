#!/bin/bash
# Get the path to the currently active virtual environment
VENV_PATH=$(dirname "$VIRTUAL_ENV")
VENV_NAME=$(basename "$VIRTUAL_ENV")

# Start a new tmux session named 'insurance_verification'
tmux new-session -d -s insurance_verification

# Split the window into left and right panes
tmux split-window -h

# Split the left pane into two panes
tmux select-pane -t insurance_verification:0.0
tmux split-window -v

# Split the right pane into three panes
tmux select-pane -t insurance_verification:0.2
tmux split-window -v
tmux split-window -v
tmux split-window -v

# Select the first pane to start
tmux select-pane -t insurance_verification:0.0

# Activate the virtual environment and run the scripts in each pane
tmux send-keys -t insurance_verification:0.0 "source $VENV_PATH/$VENV_NAME/bin/activate && python run_host.py" C-m
tmux send-keys -t insurance_verification:0.1 "source $VENV_PATH/$VENV_NAME/bin/activate && chainlit run run_ui.py --port 8001" C-m
tmux send-keys -t insurance_verification:0.2 "source $VENV_PATH/$VENV_NAME/bin/activate && python run_web_navigation_agent.py" C-m
tmux send-keys -t insurance_verification:0.3 "source $VENV_PATH/$VENV_NAME/bin/activate && python run_image_analysis_agent.py" C-m
tmux send-keys -t insurance_verification:0.4 "source $VENV_PATH/$VENV_NAME/bin/activate && python run_healthcare_task_agent.py" C-m
tmux send-keys -t insurance_verification:0.5 "source $VENV_PATH/$VENV_NAME/bin/activate && python run_group_chat_manager.py" C-m

# Attach to the session
tmux attach-session -t insurance_verification
