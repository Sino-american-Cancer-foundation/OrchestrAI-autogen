# Distributed Group Chat

This example runs a gRPC server using [GrpcWorkerAgentRuntimeHost](../../src/autogen_core/application/_worker_runtime_host.py) and instantiates three distributed runtimes using [GrpcWorkerAgentRuntime](../../src/autogen_core/application/_worker_runtime.py). These runtimes connect to the gRPC server as hosts and facilitate a round-robin distributed group chat. This example leverages the [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/ai-services/openai-service) to implement writer and editor LLM agents. Agents are instructed to provide concise answers, as the primary goal of this example is to showcase the distributed runtime rather than the quality of agent responses.

## Setup

### Setup Python Environment

1. Create a virtual environment and activate it. (e.g. `python3.12 -m venv .venv && source .venv/bin/activate`)
2. Install dependencies.

```bash
pip install "autogen-ext[openai,azure,chainlit,rich,pyyaml]"
```

### General Configuration

In the `config.yaml` file, you can configure the `client_config` section to connect the code to the Azure OpenAI Service.

### Authentication

The recommended method for authentication is through Azure Active Directory (AAD), as explained in [Model Clients - Azure AI](https://microsoft.github.io/autogen/dev/user-guide/core-user-guide/framework/model-clients.html#azure-openai). This example works with both the AAD approach (recommended) and by providing the `api_key` in the `config.yaml` file.

## Run

### Run Through Scripts

The [run.sh](./run.sh) file provides commands to run the host and agents using [tmux](https://github.com/tmux/tmux/wiki). The steps for this approach are:

1. Install tmux.
2. Activate the Python environment: `source .venv/bin/activate`.
3. Run the bash script: `./run.sh`.

Here is a screen recording of the execution:

[![Distributed Group Chat Demo with Simple UI Integration](https://img.youtube.com/vi/503QJ1onV8I/0.jpg)](https://youtu.be/503QJ1onV8I?feature=shared)

**Note**: Some `asyncio.sleep` commands have been added to the example code to make the `./run.sh` execution look sequential and visually easy to follow. In practice, these lines are not necessary.

### Run Individual Files

If you prefer to run Python files individually, follow these steps. Note that each step must be run in a different terminal process, and the virtual environment should be activated using `source .venv/bin/activate`.

1. `python run_host.py`: Starts the host and listens for agent connections.
2. `chainlit run run_ui.py  --port 8001`: Starts the Chainlit app and UI agent and listens on UI topic to display messages. We're using port 8001 as the default port 8000 is used to run host (assuming using same machine to run all of the agents)
3. `python run_editor_agent.py`: Starts the <img src="./public/avatars/editor.png" width="20" height="20" style="vertical-align:middle"> editor agent and connects it to the host.
4. `python run_writer_agent.py`: Starts the <img src="./public/avatars/writer.png" width="20" height="20" style="vertical-align:middle"> writer agent and connects it to the host.
5. `python run_group_chat_manager.py`: Run chainlit app which starts <img src="./public/avatars/group_chat_manager.png" width="20" height="20" style="vertical-align:middle"> group chat manager agent and sends the initial message to start the conversation.

## What's Going On?

The general flow of this example is as follows:

0. The UI Agent runs starts the UI App, listens for stream of messages in the UI topic and displays them in the UI.
1. The <img src="./public/avatars/group_chat_manager.png" width="20" height="20" style="vertical-align:middle"> Group Chat Manager, on behalf of <img src="./public/avatars/user.png" width="20" height="20" style="vertical-align:middle"> `User`, sends a `RequestToSpeak` request to the <img src="./public/avatars/writer.png" width="20" height="20" style="vertical-align:middle"> `writer_agent`.
2. The <img src="./public/avatars/writer.png" width="20" height="20" style="vertical-align:middle"> `writer_agent` writes a short sentence into the group chat topic.
3. The <img src="./public/avatars/editor.png" width="20" height="20" style="vertical-align:middle"> `editor_agent` receives the message in the group chat topic and updates its memory.
4. The <img src="./public/avatars/group_chat_manager.png" width="20" height="20" style="vertical-align:middle"> Group Chat Manager receives the message sent by the writer into the group chat simultaneously and sends the next participant, the <img src="./public/avatars/editor.png" width="20" height="20" style="vertical-align:middle"> `editor_agent`, a `RequestToSpeak` message.
5. The <img src="./public/avatars/editor.png" width="20" height="20" style="vertical-align:middle"> `editor_agent` sends its feedback to the group chat topic.
6. The <img src="./public/avatars/writer.png" width="20" height="20" style="vertical-align:middle"> `writer_agent` receives the feedback and updates its memory.
7. The <img src="./public/avatars/group_chat_manager.png" width="20" height="20" style="vertical-align:middle"> Group Chat Manager receives the message simultaneously and repeats the loop from step 1.

Here is an illustration of the system developed in this example:

```mermaid
graph TD;
    subgraph Host
        A1[GRPC Server]
        wt[Writer Topic]
        et[Editor Topic]
        ut[UI Topic]
        gct[Group Chat Topic]
    end
    all_agents[All Agents -  Simplified Arrows!] --> A1

    subgraph Distributed Writer Runtime
        wt -.->|2 - Subscription| writer_agent
        gct -.->|4 - Subscription| writer_agent
        writer_agent -.->|3.1 - Publish: UI Message| ut
        writer_agent -.->|3.2 - Publish: Group Chat Message| gct
    end

    subgraph Distributed Editor Runtime
        et -.->|6 - Subscription| editor_agent
        gct -.->|4 - Subscription| editor_agent
        editor_agent -.->|7.1 - Publish: UI Message| ut
        editor_agent -.->|7.2 - Publish: Group Chat Message| gct
    end

    subgraph Distributed Group Chat Manager Runtime
        gct -.->|4 - Subscription| group_chat_manager
        group_chat_manager -.->|1 - Request To Speak| wt
        group_chat_manager -.->|5 - Request To Speak| et
        group_chat_manager -.->|\* - Publish Some of to UI Message| ut
    end

    subgraph Distributed UI Runtime
        ut -.->|\* - Subscription| ui_agent
    end


    style wt fill:#beb2c3,color:#000
    style et fill:#beb2c3,color:#000
    style gct fill:#beb2c3,color:#000
    style ut fill:#beb2c3,color:#000
    style writer_agent fill:#b7c4d7,color:#000
    style editor_agent fill:#b7c4d7,color:#000
    style group_chat_manager fill:#b7c4d7,color:#000
    style ui_agent fill:#b7c4d7,color:#000

```

## TODO:

- [ ] Properly handle chat restarts. It complains about group chat manager being already registered
- [ ] Add streaming to the UI like [this example](https://docs.chainlit.io/advanced-features/streaming) when [this bug](https://github.com/microsoft/autogen/issues/4213) is resolved

```mermaid
sequenceDiagram
    participant P as Patient
    participant A as Agent
    participant Ph as Physician
    participant B as Blockchain

    %% Step 1: Patient submits medical records, creating CLINICAL_NFT_A
    P->>B: Submit medical records
    B-->>P: Mint CLINICAL_NFT_A (100% owned by Patient)

    %% Step 2: Agent processes CLINICAL_NFT_A to create CLINICAL_NFT_B
    P->>A: Share CLINICAL_NFT_A
    A->>B: Process data, link to knowledge graph
    B-->>A: Mint CLINICAL_NFT_B (Patient + Agent ownership)
    B-->>P: Notify of CLINICAL_NFT_B creation

    %% Step 3: Physician uses CLINICAL_NFT_B to make a decision, creating CLINICAL_NFT_C
    A->>Ph: Share CLINICAL_NFT_B
    Ph->>B: Make clinical decision
    B-->>Ph: Mint CLINICAL_NFT_C (Patient + Agent + Physician ownership)
    B-->>A: Notify of CLINICAL_NFT_C creation
    B-->>P: Notify of CLINICAL_NFT_C creation

    %% Step 4: Create a new NFT (CLINICAL_NFT_D) that references A, B, and C
    P->>B: Request new NFT combining A, B, C
    A->>B: Approve reference to CLINICAL_NFT_B
    Ph->>B: Approve reference to CLINICAL_NFT_C
    B-->>P: Mint CLINICAL_NFT_D (references A, B, C owned by Patient + Agent + Physician)
    B-->>A: Notify of CLINICAL_NFT_D creation
    B-->>Ph: Notify of CLINICAL_NFT_D creation
```

```mermaid
sequenceDiagram
    participant P as Patient
    participant A as Agent
    participant Ph as Physician
    participant OCS as Off-Chain Storage
    participant B as Blockchain

    %% Step 1: Patient submits medical records, creating CLINICAL_NFT_A
    Note over P,OCS: Patient encrypts medical records
    P->>OCS: Upload encrypted medical records
    OCS-->>P: Return storage reference (URI_A)
    P->>B: Request mint CLINICAL_NFT_A with URI_A
    B-->>P: Mint CLINICAL_NFT_A (owned by P, contains URI_A)

    %% Step 2: Agent processes CLINICAL_NFT_A to create CLINICAL_NFT_B
    P->>A: Share CLINICAL_NFT_A and decryption key for A
    A->>OCS: Retrieve encrypted data using URI_A from CLINICAL_NFT_A
    OCS-->>A: Provide encrypted data
    Note over A: Agent decrypts data with key
    A->>A: Process data, generate insights
    Note over A,OCS: Agent encrypts processed data
    A->>OCS: Upload encrypted processed data
    OCS-->>A: Return storage reference (URI_B)
    A->>B: Request mint CLINICAL_NFT_B with URI_B
    B-->>A: Mint CLINICAL_NFT_B (owned by P and A, contains URI_B)
    B-->>P: Notify of CLINICAL_NFT_B creation

    %% Step 3: Physician uses CLINICAL_NFT_B to make a decision, creating CLINICAL_NFT_C
    A->>Ph: Share CLINICAL_NFT_B and decryption key for B
    Ph->>OCS: Retrieve encrypted data using URI_B from CLINICAL_NFT_B
    OCS-->>Ph: Provide encrypted data
    Note over Ph: Physician decrypts data with key
    Ph->>Ph: Make clinical decision
    Note over Ph,OCS: Physician encrypts clinical decision
    Ph->>OCS: Upload encrypted clinical decision
    OCS-->>Ph: Return storage reference (URI_C)
    Ph->>B: Request mint CLINICAL_NFT_C with URI_C
    B-->>Ph: Mint CLINICAL_NFT_C (owned by P, A, Ph, contains URI_C)
    B-->>A: Notify of CLINICAL_NFT_C creation
    B-->>P: Notify of CLINICAL_NFT_C creation

    %% Step 4: Create a new NFT (CLINICAL_NFT_D) that references A, B, and C
    P->>B: Request new NFT combining A, B, C
    A->>B: Approve reference to CLINICAL_NFT_B
    Ph->>B: Approve reference to CLINICAL_NFT_C
    B-->>P: Mint CLINICAL_NFT_D (references A, B, C - owned by P, A, Ph)
    B-->>A: Notify of CLINICAL_NFT_D creation
    B-->>Ph: Notify of CLINICAL_NFT_D creation
```