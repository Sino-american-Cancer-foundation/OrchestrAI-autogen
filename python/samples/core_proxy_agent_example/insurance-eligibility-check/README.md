# Insurance Eligibility Check

A distributed multi-agent system for healthcare insurance verification with Twilio phone call integration to allow external participant join the GroupChat.

## 📁 Package Structure

```
insurance-eligibility-check/
├── __init__.py                          # Main package initialization
├── departments/                         # Organizational units
│   ├── __init__.py
│   └── orchestrator/                    # Conversation flow management
│       ├── __init__.py
│       └── orchestrator_agent.py        # OrchestratorAgent class
├── employees/                           # Specialized task agents
│   ├── __init__.py
│   ├── medical_data_agent/              # Patient data retrieval
│   │   ├── __init__.py
│   │   └── medical_data_agent.py        # MedicalDataAgent class
│   └── twilio_proxy_agent/              # Phone call handling external participant
        ├── prompts/
        │   └── phone_call_instruction.txt  # Phone agent instructions
│       ├── __init__.py
│       └── twilio_proxy_agent.py        # TwilioProxyAgent class
├── facilities/                          # Core infrastructure
│   ├── __init__.py
│   ├── core/                            # Shared utilities and base classes
│   │   ├── __init__.py                  # Exports all core functionality
│   │   ├── types.py                     # Type definitions and models
│   │   ├── base_group_chat_agent.py     # Base agent class
│   │   ├── ui_agent.py                  # UI handling agent
│   │   ├── utils.py                     # Configuration and utilities
│   │   └── publishing.py                # Message publishing functions
│   ├── runtime-gateway/
│   └── workbenches/
└── samples/                             # Working examples and configurations
    ├── config.yaml                      # System configuration
    ├── run_host.py                      # gRPC host server
    ├── run_orchestrator_agent.py        # Orchestrator runtime
    ├── run_proxy_agent.py               # Twilio proxy runtime
    ├── run_medical_data_agent.py        # Medical data runtime
    ├── run_ui.py                        # Chainlit web UI
    ├── run.sh                           # Complete system launcher
    └── chainlit.md                      # UI documentation
```

## 🎯 Design Principles

### Separation of Concerns

- **Core Definitions**: All agent classes, types, and utilities are defined in the main package structure
- **Running Examples**: Actual runtime implementations are in the `samples/` directory

### Package Organization

- **`departments/`**: High-level organizational agent (orchestrator/manager which could lead a TEAM)
- **`employees/`**: Specialized task-specific agents
- **`facilities/core/`**: Shared infrastructure, base classes, and utilities
- **`samples/`**: Working examples that demonstrate the system in action

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install required dependencies
pip install -r requirements.txt

# Set environment variables or set it in the config
export OPENAI_API_KEY="your-api-key-here"
```

### 2. Run the Complete System

```bash
cd samples/
./run.sh
```

This will start:

- gRPC host server
- Orchestrator agent
- Twilio proxy agent
- Medical data agent
- Chainlit web UI with UI agent

## 🔧 Configuration

The system uses `samples/config.yaml` for configuration:

```yaml
host:
  hostname: localhost
  port: 50051

orchestrator:
  topic_type: group_chat
  max_rounds: 5
  model_client_config:
    model: gpt-4o-mini
    api_key: ${OPENAI_API_KEY}

proxy_agent:
  topic_type: TwilioProxyAgent
  description: "Twilio proxy agent..."
  websocket_port: 8765
  # ... other config
```

## 📚 Key Components

### Core Base Classes

- **`BaseGroupChatAgent`**: Foundation for all conversation agents
- **`UIAgent`**: Handles web interface interactions
- **`OrchestratorAgent`**: Manages conversation flow and agent coordination

### Message Types

- **`GroupChatMessage`**: Core communication protocol
- **`RequestToSpeak`**: Agent activation requests
- **`MessageChunk`**: Streaming UI updates
- **`ConversationFinished`**: System termination signals

### Configuration System

- **`AppConfig`**: Complete system configuration
- **`load_config()`**: Environment-aware config loading
- **`get_serializers()`**: Message serialization utilities
