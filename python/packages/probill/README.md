# probill
```mermaid
flowchart TD
  %% Nodes
  A[Patient Clinical Data]
  B[Oncology Planning Agent</br>Policy Network]
  C[NCCN Guideline Agent]
  D[Initial Treatment Recommendation]
  E[Physician Review - HIL]
  F[Final Decision]
  G[RL Feedback Collector]
  H[RL Training Agent</br>GRPO Training Loop]
  I[Evaluation Agent</br>Validation & Safety Check]
  J[Updated Policy Network]

  %% Flow directions
  A --> B
  B -->|Query Guidelines| C
  C -->|Return Guidelines| B
  B --> D
  D --> E
  E -->|Accept/Modify| F
  F --> G
  D --> G
  A --> G
  G -->|Structured RL Feedback| H
  H -->|GRPO Training| J
  J --> I
  I -->|Safety Check Pass| B

  %% Loop annotation
  subgraph Continuous Learning Loop
    direction TB
    G --> H --> J --> I --> B
  end

  %% Style adjustments
  classDef data fill:#eef7ff,stroke:#2a6ebb,stroke-width:2px,color:#1a1a1a
  classDef agent fill:#fff5e6,stroke:#ff9900,stroke-width:2px,color:#1a1a1a
  classDef hil fill:#e7fbe7,stroke:#28a745,stroke-width:2px,color:#1a1a1a
  classDef feedback fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#1a1a1a

  class A,C data
  class B,H,I agent
  class E hil
  class G feedback
```

```mermaid
flowchart LR
    %% Define styles
    classDef orchestrator fill:#fef6e4,stroke:#b84f0c,stroke-width:1px,color:#612e02
    classDef ledger fill:#fde6e4,stroke:#b84f0c,stroke-width:1px,color:#612e02,stroke-dasharray: 5
    classDef agent fill:#e6f7ff,stroke:#2b5ea8,stroke-width:1px,color:#0b2a49
    
    %% Nodes
    T((Task)):::ledger --> O{Orchestrator\\(MDT Chair)}:::orchestrator
    O ---> TL[Task Ledger\\- Facts to look up\\- Plans & derivations]:::ledger
    O ---> PL[Progress Ledger\\- Progress checks\\- Next speaker\\- Completion?]:::ledger

    subgraph Agents
      AR[Ai Radiology Agent\\(FileSurfer/WebSurfer)]:::agent
      AP[Ai Pathology Agent\\(FileSurfer/WebSurfer)]:::agent
      AO[Ai Oncology Planning\\(RL + guidelines)]:::agent
      AB[Ai Billing Agent\\(Insurance checks)]:::agent
      AK[NCCN Knowledge Agent]:::agent
    end

    %% Flows
    O --> AR
    O --> AP
    O --> AK
    O --> AO
    O --> AB

    AR --> O
    AP --> O
    AK --> O
    AO --> O
    AB --> O

    %% Decision Structures
    O --> DC1{Progress being made?}
    DC1 -- No --> ST{Stall count\\> 2?}
    ST -- Yes --> RL(Revise Plan in\\Task Ledger)
    ST -- No --> DC1
    DC1 -- Yes --> DC2{Task Complete?}
    DC2 -- No --> O
    DC2 -- Yes --> Done([\"Task Complete\\nFinal Plan\"])

    RL --> O

    %% Classes
    class T ledger
    class O orchestrator
    class TL ledger
    class PL ledger
    class Agents agent

    %% Layout adjustments
    %% (You can tweak spacing/positions in a Mermaid editor)
```