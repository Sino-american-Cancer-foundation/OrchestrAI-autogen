from typing import List, Dict, Any
from autogen_core import ChatCompletionClient, CancellationToken
from autogen_agentchat import MagenticOneOrchestrator
from ._prompts import (
    ORCHESTRATOR_FINAL_ANSWER_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_FACTS_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT,
    ORCHESTRATOR_PROGRESS_LEDGER_PROMPT,
)


class MDTAgentOrchestrator(MagenticOneOrchestrator):
    """Custom Orchestrator specialized for MDT agent team interactions."""

    def __init__(
        self,
        name: str,
        group_topic_type: str,
        output_topic_type: str,
        participant_topic_types: List[str],
        participant_names: List[str],
        participant_descriptions: List[str],
        model_client: ChatCompletionClient,
        output_message_queue,
        max_turns: int = 20,
        max_stalls: int = 3,
    ):
        super().__init__(
            name,
            group_topic_type,
            output_topic_type,
            participant_topic_types,
            participant_names,
            participant_descriptions,
            max_turns,
            model_client,
            max_stalls,
            ORCHESTRATOR_FINAL_ANSWER_PROMPT,
            output_message_queue,
            termination_condition=None,
        )

    def _get_task_ledger_facts_prompt(self, task: str) -> str:
        return ORCHESTRATOR_TASK_LEDGER_FACTS_PROMPT.format(task=task)

    def _get_task_ledger_plan_prompt(self, team: str) -> str:
        # MDT-specific logic emphasized in planning
        prompt = f"""You are managing an MDT (Multi-Disciplinary Team) composed of the following specialized agents:
{team}

Based on typical MDT workflows, devise a short bullet-point plan for this patient case. Explicitly indicate when physician or patient input might be required."""
        return prompt

    def _get_progress_ledger_prompt(self, task: str, team: str, names: List[str]) -> str:
        # MDT-specific progress checking
        prompt = f"""We are coordinating an MDT meeting to handle the following patient case:

{task}

Team members:
{team}

Considering MDT clinical decision-making:
- Has a clinically appropriate treatment plan been finalized?
- Are we encountering repetitive or unresolved clinical, insurance, or patient-preference issues?
- Is meaningful clinical progress being made toward finalizing the treatment plan?
- Which specialist should contribute next?
- What specific clinical, insurance, or patient-preference question should they address?

Output JSON with schema:
{{
   "is_request_satisfied": {{"reason": string, "answer": boolean}},
   "is_in_loop": {{"reason": string, "answer": boolean}},
   "is_progress_being_made": {{"reason": string, "answer": boolean}},
   "next_speaker": {{"reason": string, "answer": string}},
   "instruction_or_question": {{"reason": string, "answer": string}}
}}"""
        return prompt

    async def _prepare_final_answer(self, reason: str, cancellation_token: CancellationToken) -> None:
        # Enhanced final answer logic tailored for clinical clarity
        context = self._thread_to_context()
        final_answer_prompt = f"""The MDT agents have completed reviewing the patient case:

{self._task}

Summarize the finalized MDT cancer treatment plan, including:
- Radiology findings
- Pathology classification and biomarkers
- Recommended treatment regimen with NCCN guideline validation
- Billing and insurance coverage confirmation
- Explicit notes on patient preferences incorporated

Phrase your response clearly for clinical documentation and patient communication."""

        context.append(UserMessage(content=final_answer_prompt, source=self._name))

        response = await self._model_client.create(
            self._get_compatible_context(context), cancellation_token=cancellation_token
        )

        assert isinstance(response.content, str)
        message = TextMessage(content=response.content, source=self._name)

        self._message_thread.append(message)
        await self.publish_message(
            GroupChatMessage(message=message),
            topic_id=DefaultTopicId(type=self._output_topic_type),
        )
        await self._output_message_queue.put(message)

        await self.publish_message(
            GroupChatAgentResponse(agent_response=Response(chat_message=message)),
            topic_id=DefaultTopicId(type=self._group_topic_type),
            cancellation_token=cancellation_token,
        )

        await self._signal_termination(StopMessage(content=reason, source=self._name))
