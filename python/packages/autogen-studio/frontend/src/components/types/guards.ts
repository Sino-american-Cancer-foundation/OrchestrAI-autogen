import type {
  Component,
  ComponentConfig,
  TeamConfig,
  AgentConfig,
  ModelConfig,
  ToolConfig,
  TerminationConfig,
  ChatCompletionContextConfig,
  SelectorGroupChatConfig,
  RoundRobinGroupChatConfig,
  MultimodalWebSurferConfig,
  AssistantAgentConfig,
  UserProxyAgentConfig,
  OpenAIClientConfig,
  AzureOpenAIClientConfig,
  FunctionToolConfig,
  OrTerminationConfig,
  MaxMessageTerminationConfig,
  TextMentionTerminationConfig,
  UnboundedChatCompletionContextConfig,
  AnthropicClientConfig,
  AndTerminationConfig,
  McpHostAgentConfig,
  WorkbenchConfig,
  McpsWorkbenchConfig,
} from "./datamodel";

// Provider constants
const PROVIDERS = {
  // Teams
  ROUND_ROBIN_TEAM: "autogen_agentchat.teams.RoundRobinGroupChat",
  SELECTOR_TEAM: "autogen_agentchat.teams.SelectorGroupChat",

  // Agents
  ASSISTANT_AGENT: "autogen_agentchat.agents.AssistantAgent",
  USER_PROXY: "autogen_agentchat.agents.UserProxyAgent",
  WEB_SURFER: "autogen_ext.agents.web_surfer.MultimodalWebSurfer",
  MCP_HOST_AGENT: "probill.agents.McpHostAgent",

  // Models
  OPENAI: "autogen_ext.models.openai.OpenAIChatCompletionClient",
  AZURE_OPENAI: "autogen_ext.models.openai.AzureOpenAIChatCompletionClient",
  ANTHROPIC: "autogen_ext.models.anthropic.AnthropicChatCompletionClient",

  // Tools
  FUNCTION_TOOL: "autogen_core.tools.FunctionTool",
  
  // Workbenches
  MCPS_WORKBENCH: "probill.tools.mcp.McpsWorkbench",

  // Termination
  OR_TERMINATION: "autogen_agentchat.base.OrTerminationCondition",
  AND_TERMINATION: "autogen_agentchat.base.AndTerminationCondition",
  MAX_MESSAGE: "autogen_agentchat.conditions.MaxMessageTermination",
  TEXT_MENTION: "autogen_agentchat.conditions.TextMentionTermination",

  // Contexts
  UNBOUNDED_CONTEXT: "autogen_core.model_context.UnboundedChatCompletionContext",
} as const;

// Provider type
export type Provider = (typeof PROVIDERS)[keyof typeof PROVIDERS];

export function isComponent(value: any): value is Component<ComponentConfig> {
  return (
    value &&
    typeof value === "object" &&
    "provider" in value &&
    "component_type" in value &&
    "config" in value
  );
}

// Generic component type guard without using ProviderToConfig
function isComponentOfType(
  component: Component<ComponentConfig>,
  provider: Provider
): boolean {
  return component.provider === provider;
}

// Base component type guards
export function isTeamComponent(
  component: Component<ComponentConfig>
): component is Component<TeamConfig> {
  return component.component_type === "team";
}

export function isAgentComponent(
  component: Component<ComponentConfig>
): component is Component<AgentConfig> {
  return component.component_type === "agent";
}

export function isModelComponent(
  component: Component<ComponentConfig>
): component is Component<ModelConfig> {
  return component.component_type === "model";
}

export function isToolComponent(
  component: Component<ComponentConfig>
): component is Component<ToolConfig> {
  return component.component_type === "tool";
}

export function isTerminationComponent(
  component: Component<ComponentConfig>
): component is Component<TerminationConfig> {
  return component.component_type === "termination";
}

// Team provider guards with proper type narrowing
export function isRoundRobinTeam(
  component: Component<ComponentConfig>
): component is Component<RoundRobinGroupChatConfig> {
  return isComponentOfType(component, PROVIDERS.ROUND_ROBIN_TEAM);
}

export function isSelectorTeam(
  component: Component<ComponentConfig>
): component is Component<SelectorGroupChatConfig> {
  return isComponentOfType(component, PROVIDERS.SELECTOR_TEAM);
}

// Agent provider guards with proper type narrowing
export function isAssistantAgent(
  component: Component<ComponentConfig>
): component is Component<AssistantAgentConfig> {
  return isComponentOfType(component, PROVIDERS.ASSISTANT_AGENT);
}

export function isUserProxyAgent(
  component: Component<ComponentConfig>
): component is Component<UserProxyAgentConfig> {
  return isComponentOfType(component, PROVIDERS.USER_PROXY);
}

export function isWebSurferAgent(
  component: Component<ComponentConfig>
): component is Component<MultimodalWebSurferConfig> {
  return isComponentOfType(component, PROVIDERS.WEB_SURFER);
}

export function isMcpHostAgent(
  component: Component<ComponentConfig>
): component is Component<McpHostAgentConfig> {
  return isComponentOfType(component, PROVIDERS.MCP_HOST_AGENT);
}

// Model provider guards with proper type narrowing
export function isOpenAIModel(
  component: Component<ComponentConfig>
): component is Component<OpenAIClientConfig> {
  return isComponentOfType(component, PROVIDERS.OPENAI);
}

export function isAzureOpenAIModel(
  component: Component<ComponentConfig>
): component is Component<AzureOpenAIClientConfig> {
  return isComponentOfType(component, PROVIDERS.AZURE_OPENAI);
}

export function isAnthropicModel(
  component: Component<ComponentConfig>
): component is Component<AnthropicClientConfig> {
  return component.provider === PROVIDERS.ANTHROPIC;
}

// Tool provider guards with proper type narrowing
export function isFunctionTool(
  component: Component<ComponentConfig>
): component is Component<FunctionToolConfig> {
  return isComponentOfType(component, PROVIDERS.FUNCTION_TOOL);
}

// Termination provider guards with proper type narrowing
export function isOrTermination(
  component: Component<ComponentConfig>
): component is Component<OrTerminationConfig> {
  return isComponentOfType(component, PROVIDERS.OR_TERMINATION);
}

// is Or or And termination
export function isCombinationTermination(
  component: Component<ComponentConfig>
): component is Component<OrTerminationConfig | AndTerminationConfig> {
  return (
    isComponentOfType(component, PROVIDERS.OR_TERMINATION) ||
    isComponentOfType(component, PROVIDERS.AND_TERMINATION)
  );
}

export function isAndTermination(
  component: Component<ComponentConfig>
): component is Component<AndTerminationConfig> {
  return isComponentOfType(component, PROVIDERS.AND_TERMINATION);
}

export function isMaxMessageTermination(
  component: Component<ComponentConfig>
): component is Component<MaxMessageTerminationConfig> {
  return isComponentOfType(component, PROVIDERS.MAX_MESSAGE);
}

export function isTextMentionTermination(
  component: Component<ComponentConfig>
): component is Component<TextMentionTerminationConfig> {
  return isComponentOfType(component, PROVIDERS.TEXT_MENTION);
}

// Workbench provider guards with proper type narrowing
export function isMcpsWorkbench(
  component: Component<ComponentConfig>
): component is Component<McpsWorkbenchConfig> {
  return isComponentOfType(component, PROVIDERS.MCPS_WORKBENCH);
}

export function isWorkbenchComponent(
  component: Component<ComponentConfig>
): component is Component<WorkbenchConfig> {
  return component.component_type === "workbench";
}

// Context provider guards with proper type narrowing
export function isUnboundedContext(
  component: Component<ComponentConfig>
): component is Component<UnboundedChatCompletionContextConfig> {
  return isComponentOfType(component, PROVIDERS.UNBOUNDED_CONTEXT);
}

// Runtime assertions
export function assertComponentType(
  component: Component<ComponentConfig>,
  provider: Provider
): asserts component is Component<any> {
  if (!isComponentOfType(component, provider)) {
    throw new Error(
      `Expected component with provider ${provider}, got ${component.provider}`
    );
  }
}

export { PROVIDERS };
