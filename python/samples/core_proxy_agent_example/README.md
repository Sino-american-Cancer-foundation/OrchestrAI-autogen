# Core Proxy Agent Example

A distributed multi-agent system demonstrating healthcare conversation management with external participant integration via phone calls.

## **🏗️ Architecture (Fixed)**

This implementation now follows the **correct distributed group chat pattern** to avoid infinite loops:

### **Topic Architecture**

- **`group_chat`**: Central topic for all GroupChatMessage (orchestrator subscribes here)
- **`TwilioProxyAgent`**: Agent-specific topic for RequestToSpeak messages
- **`MedicalDataAgent`**: Agent-specific topic for RequestToSpeak messages
- **`ui_events`**: UI-specific topic for MessageChunk streaming

### **Message Flow**

1. **User** → UI → `group_chat` topic (`GroupChatMessage`)
2. **OrchestratorAgent** processes `GroupChatMessage` → decides next speaker
3. **OrchestratorAgent** → sends `RequestToSpeak` to specific agent topic
4. **Agent** responds with LLM completion → sends back to `group_chat` topic
5. **Repeat** until conversation concludes

### **Agent Patterns**

#### **OrchestratorAgent** (GroupChatManager Pattern)

- **Subscribes to**: `group_chat` topic only
- **Processes**: `GroupChatMessage` (user messages only)
- **Sends**: `RequestToSpeak` to specific agent topics
- **Never responds to agent messages** (prevents infinite loops)

#### **TwilioProxyAgent & MedicalDataAgent** (BaseGroupChatAgent Pattern)

- **Subscribes to**: BOTH `group_chat` (history) AND own topic (RequestToSpeak)
- **Processes**: `GroupChatMessage` (for context) + `RequestToSpeak` (to respond)
- **Only responds** when receiving `RequestToSpeak`

## **🚀 Components**

### **OrchestratorAgent**

- **Role**: Conversation flow manager
- **Function**: Decides which agent should respond next
- **Pattern**: GroupChatManager (no infinite loops)

### **TwilioProxyAgent**

- **Role**: External participant connector via phone calls
- **Features**:
  - Phone number detection via regex
  - MCP tool integration for calls
  - WebSocket server for audio (simulated)
  - Mode switching (INACTIVE → ACTIVE)
  - **Graceful call termination** when conversation finishes
- **Pattern**: BaseGroupChatAgent with enhanced phone functionality

### **MedicalDataAgent**

- **Role**: Patient medical information provider
- **Features**:
  - Simulated medical database lookup
  - Patient data retrieval with search delay
  - Comprehensive medical history reporting
- **Pattern**: BaseGroupChatAgent with medical data integration

### **UIAgent**

- **Role**: Chainlit web interface handler
- **Features**:
  - Real-time message streaming
  - User input processing
  - Agent response display

## **📋 Message Types**

### **GroupChatMessage**

```python
class GroupChatMessage(BaseModel):
    body: LLMMessage  # UserMessage or AssistantMessage
```

### **RequestToSpeak**

```python
class RequestToSpeak(BaseModel):
    pass  # Simple trigger message
```

### **ConversationFinished**

```python
class ConversationFinished(BaseModel):
    reason: str  # Reason for conversation completion
```

### **MessageChunk**

```python
class MessageChunk(BaseModel):
    message_id: str
    text: str
    author: str
    finished: bool
```

## **⚙️ Configuration**

### **config.yaml**

```yaml
orchestrator:
  topic_type: group_chat # Central hub
  max_rounds: 5

proxy_agent:
  topic_type: TwilioProxyAgent # Specific agent topic
  description: "Twilio proxy agent that handles phone calls..."
  system_message: "You are a TwilioProxyAgent..."

medical_data_agent:
  topic_type: MedicalDataAgent # Specific agent topic
  description: "Medical data agent..."
  system_message: "You are a MedicalDataAgent..."

ui_agent:
  topic_type: ui_events # UI streaming topic
```

## **🏃‍♂️ Running the System**

### **Option 1: All Components**

```bash
./run.sh
```

### **Option 2: Individual Components**

**Terminal 1: Host**

```bash
python run_host.py
```

**Terminal 2: Orchestrator**

```bash
python run_orchestrator_agent.py
```

**Terminal 3: Proxy Agent**

```bash
python run_proxy_agent.py
```

**Terminal 4: Medical Data Agent**

```bash
python run_medical_data_agent.py
```

**Terminal 5: UI (Chainlit)**

```bash
python run_ui.py
```

## **💬 Example Interaction**

1. **User Input**: "I need to reach John Smith at 555-0123 about his recent diabetes follow-up visit."

2. **OrchestratorAgent** → Detects phone number context → Selects **TwilioProxyAgent**

3. **TwilioProxyAgent** → Detects phone number → Initiates call → Reports connection status

4. **OrchestratorAgent** → Selects **MedicalDataAgent** for patient info

5. **MedicalDataAgent** → Retrieves John Smith's medical data → Provides comprehensive report

6. **Conversation continues** until orchestrator decides to finish

7. **OrchestratorAgent** → Broadcasts `ConversationFinished` message to all agents

8. **TwilioProxyAgent** → Receives notification → Sends `end_call` to active WebSocket sessions → Gracefully terminates phone calls

## **🔧 Key Fixes Implemented**

### **❌ Previous Issues**

- All agents subscribed to `"default"` topic → everyone got all messages
- OrchestratorAgent processed its own responses → infinite loops
- Incorrect GroupChatMessage structure → type mismatches
- Wrong agent inheritance patterns → broken message flow

### **✅ Solutions Applied**

- **Proper topic separation**: Each agent has specific topic + group chat subscription
- **GroupChatManager pattern**: Orchestrator only processes user messages
- **Correct message structure**: GroupChatMessage contains LLMMessage body
- **BaseGroupChatAgent pattern**: Agents respond only to RequestToSpeak

## **🎯 Features Preserved**

- ✅ **TwilioProxyAgent** phone call detection & WebSocket integration
- ✅ **Graceful call termination** when conversation completes
- ✅ **MedicalDataAgent** patient data lookup with realistic delay
- ✅ **Chainlit UI** with streaming message chunks
- ✅ **MCP tool integration** for external phone calls
- ✅ **Healthcare domain logic** with patient data management

## **🔚 Conversation Termination Flow**

The system now includes **graceful conversation termination** with automatic call cleanup:

### **When Orchestrator Decides "FINISH"**

1. **OrchestratorAgent** determines conversation is complete (LLM returns "FINISH: {reason}")
2. **Parses dynamic finish reason** from LLM response instead of using generic message
3. **Publishes contextual finish message to UI** with specific accomplishments
4. **NEW**: Broadcasts `ConversationFinished` message to all participant agents
5. **TwilioProxyAgent** receives notification and:
   - Identifies all active phone call sessions
   - Sends `end_call` WebSocket message to each active session
   - WebSocket server responds with `call_ended` message
   - Agent processes `call_ended` and cleans up session resources
   - Switches back to INACTIVE mode when no sessions remain

### **Benefits**

- ✅ **No hanging calls** - External participants are properly disconnected
- ✅ **Dynamic finish messages** - Contextual completion summaries instead of generic text
- ✅ **Clean resource management** - WebSocket sessions are gracefully closed
- ✅ **Proper state transitions** - TwilioProxyAgent returns to INACTIVE mode
- ✅ **Extensible pattern** - Other agents can also respond to ConversationFinished

## **📊 Architecture Validation**

The system now follows the **proven distributed group chat pattern**:

1. **No infinite loops** - Orchestrator doesn't process agent responses
2. **Proper message routing** - Each agent gets only relevant messages
3. **Correct subscriptions** - Dual subscriptions for history + control
4. **Type safety** - Proper LLMMessage structure throughout
5. **Scalable design** - Easy to add new agents following patterns
6. **Graceful termination** - Proper cleanup when conversations end

## **🔗 Related Examples**

- `core_distributed-group-chat/`: Reference implementation for the architecture pattern
- `agentchat_*/`: Other agent chat examples
- `core_*/`: Core framework examples
