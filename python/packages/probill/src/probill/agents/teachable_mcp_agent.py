from typing import Any, Dict, List, Sequence, Callable, Awaitable
from typing_extensions import Self

from autogen_core.model_context import ChatCompletionContext
from autogen_core.memory import Memory
from autogen_core.tools import BaseTool
from autogen_core.models import ChatCompletionClient, SystemMessage

from autogen_agentchat.base import Handoff as HandoffBase
from autogen_ext.tools.mcp import McpServerParams
from autogen_ext.experimental.task_centric_memory import MemoryController
from autogen_ext.experimental.task_centric_memory.utils import Teachability

from .mcp_host_agent import McpHostAgent, McpHostAgentConfig

class TeachableMcpAgentConfig(McpHostAgentConfig):
    """Configuration for the Teachable MCP Agent."""
    reset_memory: bool = False

class TeachableMcpAgent(McpHostAgent):
    """
    TeachableMcpAgent extends McpHostAgent with the ability to learn new skills and behaviors.
    It can store learned information and modify its behavior based on user interactions using 
    task-centric memory for persistent learning across conversations.
    """
    component_type = "agent"
    component_config_schema = TeachableMcpAgentConfig
    component_provider_override = "probill.agents.TeachableMcpAgent"

    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        *,
        tools: List[BaseTool[Any, Any] | Callable[..., Any] | Callable[..., Awaitable[Any]]] | None = None,
        handoffs: List[HandoffBase | str] | None = None,
        model_context: ChatCompletionContext | None = None,
        description: str | None = None,
        server_params: McpServerParams | None = None,
        system_message: str | None = None,
        reflect_on_tool_use: bool = False,
        model_client_stream: bool = False,
        tool_call_summary_format: str = "{result}",
        memory: Sequence[Memory] | None = None,
        metadata: Dict[str, str] | None = None,
        reset_memory: bool = False,
    ):
        # Initialize task-centric memory components
        memory_controller = MemoryController(
            reset=reset_memory,
            client=model_client
        )
        teachability = Teachability(
            memory_controller=memory_controller,
            name=f"{name}_memory"
        )

        # Include teachability in memory if no memory is provided
        if memory is None:
            memory = [teachability]
        else:
            memory = list(memory) + [teachability]

        super().__init__(
            name=name,
            model_client=model_client,
            tools=tools,
            handoffs=handoffs,
            model_context=model_context,
            description=description or "A teachable MCP agent that can learn new skills and behaviors.",
            server_params=server_params,
            system_message=system_message or "You are a helpful AI assistant with MCP capabilities.",
            reflect_on_tool_use=reflect_on_tool_use,
            model_client_stream=model_client_stream,
            tool_call_summary_format=tool_call_summary_format,
            memory=memory,
            metadata=metadata,
        )        
        # Update system messages with learning capabilities
        # if self._system_messages:
        #     self._system_messages[0].content = f"{self._system_messages[0].content}\n{self._learning_system_message}"
        #     for skill, description in self._learned_skills.items():
        #         self._system_messages[0].content = f"{self._system_messages[0].content}\nLearned skill - {skill}: {description}"

    async def learn_skill(self, skill_name: str, skill_description: str) -> None:
        """Learn a new skill or update an existing one."""
        self._learned_skills[skill_name] = skill_description
        if self._system_messages:
            self._system_messages[0].content = f"{self._system_messages[0].content}\nLearned skill - {skill_name}: {skill_description}"
        await self._model_context.clear()  # Clear context to ensure new skill is incorporated

    async def forget_skill(self, skill_name: str) -> bool:
        """Forget a learned skill. Returns True if the skill was found and removed."""
        if skill_name in self._learned_skills:
            del self._learned_skills[skill_name]
            if self._system_messages:
                # Rebuild system message without the forgotten skill
                base_message = self._system_messages[0].content.split("\n")[0]
                self._system_messages[0].content = f"{base_message}\n{self._learning_system_message}"
                for skill, description in self._learned_skills.items():
                    self._system_messages[0].content = f"{self._system_messages[0].content}\nLearned skill - {skill}: {description}"
            await self._model_context.clear()  # Clear context to ensure skill removal is incorporated
            return True
        return False

    def list_learned_skills(self) -> Dict[str, str]:
        """Return a dictionary of all learned skills and their descriptions."""
        return self._learned_skills.copy()
    
    def _to_config(self) -> TeachableMcpAgentConfig:
        """Convert the teachable agent to its configuration."""
        # Save current memory
        original_memory = self._memory
        # Remove MemoryController and Teachability instances
        self._memory = [
            memory 
            for memory in self._memory 
            if not isinstance(memory, (Teachability, MemoryController))
        ] if self._memory else None
        # Get base configuration from parent class
        base_config = super()._to_config()
        # Restore original memory
        self._memory = original_memory
        
        # Create new config with our specific memory handling
        return TeachableMcpAgentConfig(
            **{
            **base_config.__dict__,
            'reset_memory': False  # Always save as False to preserve memory by default
            }
        )

    @classmethod
    def _from_config(cls, config: TeachableMcpAgentConfig) -> Self:
        """Create an instance of TeachableMcpAgent from its configuration."""
        return cls(
            name=config.name,
            model_client=ChatCompletionClient.load_component(config.model_client),
            tools=[BaseTool.load_component(tool) for tool in config.tools] if config.tools else None,
            handoffs=config.handoffs,
            model_context=ChatCompletionContext.load_component(config.model_context) if config.model_context else None,
            memory=[Memory.load_component(memory) for memory in config.memory] if config.memory else None,
            description=config.description,
            system_message=config.system_message,
            model_client_stream=config.model_client_stream,
            reflect_on_tool_use=config.reflect_on_tool_use,
            tool_call_summary_format=config.tool_call_summary_format,
            metadata=config.metadata,
            server_params=config.server_params,
            reset_memory=config.reset_memory,
        )