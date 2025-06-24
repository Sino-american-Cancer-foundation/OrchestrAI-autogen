# Insurance Eligibility Check System 🏥

Welcome to the **Insurance Eligibility Check** distributed multi-agent system! This system demonstrates how AI agents can work together to handle complex healthcare verification tasks involving external participants via phone calls.

## 🎭 System Overview

This system uses multiple specialized agents:

- **🎯 Orchestrator Agent**: Manages conversation flow and coordinates between agents
- **📞 Twilio Proxy Agent**: Handles phone calls to external participants using real-time voice communication
- **🏥 Medical Data Agent**: Retrieves and manages patient medical information and insurance details
- **🖥️ UI Agent**: Provides this web interface for interaction

## 📋 What You Can Do

### 📞 Request Phone Calls

- _"I need to call John Smith at +15551234567 about his insurance eligibility"_
- _"Please reach the insurance provider at 555-0123 to verify coverage"_
- _"Call the patient at their callback number to discuss the medical plan"_

### 🏥 Get Medical Information

- _"Show me John Smith's medical history and current medications"_
- _"What insurance information do we have for patient E01222465?"_
- _"I need the physician contact details for this patient"_

### 🔄 Complex Workflows

- _"I need to verify insurance eligibility for John Smith and then call him with the results"_
- _"Get the patient's medical data and call their insurance company to confirm coverage"_

## 🚀 Try These Examples

**Basic Medical Query:**

> _"What medical information do we have available?"_

**Phone Call Request:**

> _"I need to reach John Smith at +15551234567 about his recent diabetes follow-up visit."_

**Insurance Verification:**

> _"Please call HealthFirst Insurance at 213-284-1509 to verify John Smith's coverage for his diabetes medications."_

---

💡 **Tip**: The system will automatically create a plan and coordinate between agents to fulfill your requests!
