from autogen_core import MessageContext, message_handler
from autogen_core.models import UserMessage, AssistantMessage, SystemMessage, ChatCompletionClient
from rich.markdown import Markdown

from facilities.core.base_group_chat_agent import BaseGroupChatAgent
from facilities.core.types import RequestToSpeak, UIAgentConfig, PatientData
from facilities.core.publishing import publish_message_to_ui_and_backend


class MedicalDataAgent(BaseGroupChatAgent):
    """Agent that retrieves medical data for patients."""
    
    def __init__(
        self,
        description: str,
        group_chat_topic_type: str,
        model_client: ChatCompletionClient,
        system_message: str,
        ui_config: UIAgentConfig,
    ) -> None:
        super().__init__(description, group_chat_topic_type, model_client, system_message, ui_config)
    
    @message_handler
    async def handle_request_to_speak(self, message: RequestToSpeak, ctx: MessageContext) -> None:
        """Enhanced request to speak handler with medical data lookup."""
        # Add medical data context to system message
        enhanced_system_content = f"""{self._system_message.content}

When responding, you can access patient medical data. If the conversation mentions patients or medical information needs, 
provide relevant medical data from your database. Simulate a brief search delay before responding with detailed patient information."""

        enhanced_system_message = SystemMessage(content=enhanced_system_content)
        
        self._chat_history.append(
            UserMessage(content=f"Transferred to {self.id.type}, adopt the persona immediately.", source="system")
        )
        
        # Get patient data and include in response
        patient_data = await self._get_patient_data()
            
        # Add patient data context
        medical_context = f"""
Current patient data available:
Patient Name: {patient_data.name} (Member ID: {patient_data.patient_id})
Age: {patient_data.age}
Gender: {patient_data.gender}
Date of Birth: {patient_data.date_of_birth}
Physician: {patient_data.physician} (NPI: {patient_data.npi})
Contact/Call back number: {patient_data.callback_number}
Medical History: {', '.join(patient_data.medical_history)}
Current Medications: {', '.join(patient_data.current_medications)}
Insurance: {patient_data.insurance_info}

Use this information to provide helpful medical context in your response.
"""
        
        medical_context_msg = UserMessage(content=medical_context, source="system")
        completion = await self._model_client.create([enhanced_system_message] + self._chat_history + [medical_context_msg])
        assert isinstance(completion.content, str)
        self._chat_history.append(AssistantMessage(content=completion.content, source=self.id.type))

        console_message = f"\n{'-'*80}\n**{self.id.type}**: {completion.content}"
        self.console.print(Markdown(console_message))
            
        await publish_message_to_ui_and_backend(
            runtime=self,
            source=self.id.type,
            user_message=completion.content,
            ui_config=self._ui_config,
            group_chat_topic_type=self._group_chat_topic_type,
        )
    
    async def _get_patient_data(self) -> PatientData:
        """Simulate retrieving patient data from medical database."""
        return PatientData(
            patient_id="E01222465",
            name="John Smith",
            age=38,
            gender="Male",
            date_of_birth="August 23, 1987",
            physician="Dr. Julius Caesar",
            npi="168719879",
            callback_number="554-187-8789",
            medical_history=[
                "Type 2 Diabetes",
                "Hypertension",
                "Seasonal Allergies"
            ],
            current_medications=[
                "Metformin 500mg",
                "Lisinopril 10mg",
                "Cetirizine 10mg"
            ],
            insurance_info={
                "provider": "HealthFirst Insurance",
                "customer_service_phone": "2132841509",
                "customer_service_email": "customer_service@healthfirst.com"
            }
        )