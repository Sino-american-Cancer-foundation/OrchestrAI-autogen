# Wrapper Agent Example

This example demonstrates a simplified multi-agent architecture that consolidates orchestration logic into a single **WrapperAgent** while leveraging MCP (Model Context Protocol) tools for all external operations.

## Architecture Overview

### Key Components

1. **WrapperAgent** - The central orchestrator that:

   - Intercepts all user requests
   - Detects flow type (single response vs WebSocket conversation)
   - Manages WebSocket sessions for real-time calls
   - Routes responses appropriately
   - Generates conversation summaries

2. **UIAgent** - Handles UI message streaming (unchanged from original)

3. **MCP Server** - Provides tools including:
   - `make_call` - Initiates phone calls
   - `transcribe_audio` - Converts audio to text
   - `ask_ai_agent` - AI-powered responses using GPT-4o-mini

### Simplified Runtime Structure

Only 3 runtimes instead of 5:

- **Host** - The gRPC host runtime
- **UI** - Chainlit-based user interface
- **WrapperAgent** - Single orchestrator (replaces GroupChatManager + FormatProxyAgent)

## Design Benefits

1. **Simplified Architecture** - Single point of orchestration
2. **Unified Tool Interface** - Everything through MCP tools
3. **Better Separation of Concerns** - Routing logic vs domain expertise
4. **Enhanced Flexibility** - Easy to add new domain agents as MCP tools
5. **Cleaner State Management** - Centralized in WrapperAgent

## Flow Types

### Single Response Flow

```
User → WrapperAgent → ask_ai_agent (MCP) → Response → User
```

### WebSocket Conversation Flow

```
User → WrapperAgent → make_call (MCP) → WebSocket Session →
[Loop: Audio → transcribe_audio → ask_ai_agent → WebSocket] →
Summary → User
```

## Prerequisites

1. Python environment with required packages
2. MCP server running with the required tools
3. tmux installed for running multiple processes
4. OpenAI API key set in environment for the MCP server

## Running the Example

1. **Start your MCP server** (in a separate terminal):

   ```bash
   # Set your OpenAI API key
   export OPENAI_API_KEY="your-api-key-here"

   # Run the MCP server
   python your_mcp_server.py --port 8931
   ```

2. Make the run script executable:

   ```bash
   chmod +x run.sh
   ```

3. Run the example:
   ```bash
   ./run.sh
   ```

This will start 3 tmux panes:

- Pane 0: Host runtime
- Pane 1: Chainlit UI (port 8002)
- Pane 2: Wrapper Agent

4. Open your browser to `http://localhost:8002` to interact with the system

## MCP Server Tools

The MCP server provides these tools:

### ask_ai_agent

Provides AI-powered responses using GPT-4o-mini:

```python
{
    "question": "Your question here"
}
# Returns: {"status": "success", "response": "AI response", "model": "gpt-4o-mini"}
```

### make_call

Initiates phone calls:

```python
{
    "to_number": "+1234567890",
    "information": "Context for the call"
}
# Returns: {"status": "success", "call_sid": "...", "websocket_url": "..."}
```

### transcribe_audio

Transcribes audio to text:

```python
{
    "audio_data": "base64_encoded_audio",
    "model": "whisper"
}
# Returns: {"status": "success", "text": "transcribed text"}
```

## Configuration

Edit `config.yaml` to adjust:

- Host address/port
- Topic types
- MCP server URL
- UI streaming delays

## Key Differences from Original Architecture

1. **No separate DomainAgent runtime** - Functionality moved to MCP tool
2. **No GroupChatManager** - Logic consolidated into WrapperAgent
3. **Direct MCP tool calls** - No inter-agent messaging for domain queries
4. **Simplified configuration** - Fewer components to configure
5. **Reduced complexity** - 40% fewer files and runtimes

## Example Interactions

### Direct Question

```
User: "Tell me about health insurance"
WrapperAgent → ask_ai_agent → Response about health insurance
```

### Phone Call

```
User: "Call to check eligibility for patient John Doe"
WrapperAgent → make_call → WebSocket connection established
[Real-time conversation with transcription and AI responses]
→ Summary generated at end
```

## Extending the System

To add new capabilities:

1. **Add new MCP tools** - Implement additional tools in your MCP server
2. **Enhance flow detection** - Improve `_detect_flow_type()` with ML models
3. **Add new flow types** - Extend the `FlowType` enum and implement handlers
4. **Custom routing logic** - Modify `_route_response()` for complex scenarios

## Troubleshooting

- **"ask_ai_agent tool not found"**: Make sure your MCP server is running on port 8931
- **No AI responses**: Check that OPENAI_API_KEY is set in the MCP server environment
- **Connection errors**: Verify the MCP server URL in config.yaml matches your server
