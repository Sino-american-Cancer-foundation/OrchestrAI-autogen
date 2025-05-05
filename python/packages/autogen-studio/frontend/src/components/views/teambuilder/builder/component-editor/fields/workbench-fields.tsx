import React, { useCallback, useState } from "react";
import { Input, Button, Tooltip, List, Select } from "antd";
import { PlusCircle, MinusCircle, Edit, HelpCircle } from "lucide-react";
import {
  Component,
  ComponentConfig,
  McpsServerParams,
  McpsWorkbenchConfig,
} from "../../../../../types/datamodel";
import { isMcpsWorkbench } from "../../../../../types/guards";
import DetailGroup from "../detailgroup";

const { TextArea } = Input;

interface WorkbenchFieldsProps {
  component: Component<ComponentConfig>;
  onChange: (updates: Partial<Component<ComponentConfig>>) => void;
}

interface ServerParamsFormState {
  serverId: string;
  serverType: "stdio" | "sse";
  // Stdio specific
  command?: string;
  args?: string;
  // SSE specific
  url?: string;
}

const InputWithTooltip: React.FC<{
  label: string;
  tooltip: string;
  children: React.ReactNode;
  required?: boolean;
}> = ({ label, tooltip, children, required }) => (
  <label className="block">
    <div className="flex items-center gap-2 mb-1">
      <span className="text-sm font-medium text-primary">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </span>
      <Tooltip title={tooltip}>
        <HelpCircle className="w-4 h-4 text-secondary" />
      </Tooltip>
    </div>
    {children}
  </label>
);

export const WorkbenchFields: React.FC<WorkbenchFieldsProps> = ({
  component,
  onChange,
}) => {
  const [isAddingServer, setIsAddingServer] = useState(false);
  const [serverParams, setServerParams] = useState<ServerParamsFormState>({
    serverId: "",
    serverType: "stdio",
    command: "",
    args: "",
  });
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  if (!isMcpsWorkbench(component)) return null;

  const handleComponentUpdate = useCallback(
    (updates: Partial<Component<ComponentConfig>>) => {
      onChange({
        ...component,
        ...updates,
        config: {
          ...component.config,
          ...(updates.config || {}),
        },
      });
    },
    [component, onChange]
  );

  const handleConfigUpdate = useCallback(
    (field: string, value: any) => {
      handleComponentUpdate({
        config: {
          ...component.config,
          [field]: value,
        },
      });
    },
    [component, handleComponentUpdate]
  );

  const handleAddServer = () => {
    const { serverId, serverType, command, args, url } = serverParams;
    
    if (!serverId) {
      // Show error
      return;
    }

    let serverParamsObj: any = {};
    
    if (serverType === "stdio") {
      if (!command) {
        // Show error
        return;
      }
      
      serverParamsObj = {
        command,
        args: args ? args.split(" ") : [],
      };
    } else if (serverType === "sse") {
      if (!url) {
        // Show error
        return;
      }
      
      serverParamsObj = {
        url,
      };
    }

    const newServerParam: McpsServerParams = {
      server_id: serverId,
      server_params: serverParamsObj,
    };

    const serverParamsList = [...(component.config.server_params_list || [])];
    
    if (editingIndex !== null) {
      // Update existing
      serverParamsList[editingIndex] = newServerParam;
    } else {
      // Add new
      serverParamsList.push(newServerParam);
    }

    handleConfigUpdate("server_params_list", serverParamsList);
    
    // Reset form
    setServerParams({
      serverId: "",
      serverType: "stdio",
      command: "",
      args: "",
    });
    setIsAddingServer(false);
    setEditingIndex(null);
  };

  const handleRemoveServer = (index: number) => {
    const serverParamsList = [...(component.config.server_params_list || [])];
    serverParamsList.splice(index, 1);
    handleConfigUpdate("server_params_list", serverParamsList);
  };

  const handleEditServer = (index: number) => {
    const server = component.config.server_params_list[index];
    const serverType = 
      "command" in server.server_params ? "stdio" : "sse";

    let newParams: ServerParamsFormState = {
      serverId: server.server_id,
      serverType,
    };

    if (serverType === "stdio") {
      newParams.command = server.server_params.command;
      newParams.args = Array.isArray(server.server_params.args) 
        ? server.server_params.args.join(" ") 
        : "";
    } else {
      newParams.url = server.server_params.url;
    }

    setServerParams(newParams);
    setEditingIndex(index);
    setIsAddingServer(true);
  };

  const renderServerForm = () => {
    return (
      <div className="space-y-4 mt-4 p-4 border border-tertiary rounded-md">
        <InputWithTooltip 
          label="Server ID" 
          tooltip="A unique identifier for this server"
          required
        >
          <Input
            value={serverParams.serverId}
            onChange={(e) => setServerParams({ ...serverParams, serverId: e.target.value })}
            placeholder="E.g., github_server, playwright_server, etc."
          />
        </InputWithTooltip>

        <InputWithTooltip 
          label="Server Type" 
          tooltip="The type of MCP server connection"
          required
        >
          <Select
            value={serverParams.serverType}
            onChange={(value) => setServerParams({ ...serverParams, serverType: value })}
            className="w-full"
          >
            <Select.Option value="stdio">StdIO Server</Select.Option>
            <Select.Option value="sse">SSE Server</Select.Option>
          </Select>
        </InputWithTooltip>

        {serverParams.serverType === "stdio" && (
          <>
            <InputWithTooltip 
              label="Command" 
              tooltip="The command to run the MCP server"
              required
            >
              <Input
                value={serverParams.command}
                onChange={(e) => setServerParams({ ...serverParams, command: e.target.value })}
                placeholder="E.g., npx, docker, uvx"
              />
            </InputWithTooltip>

            <InputWithTooltip 
              label="Arguments" 
              tooltip="Command line arguments (space separated)"
            >
              <Input
                value={serverParams.args}
                onChange={(e) => setServerParams({ ...serverParams, args: e.target.value })}
                placeholder="E.g., @playwright/mcp@latest --headless"
              />
            </InputWithTooltip>
          </>
        )}

        {serverParams.serverType === "sse" && (
          <InputWithTooltip 
            label="URL" 
            tooltip="The URL of the SSE server"
            required
          >
            <Input
              value={serverParams.url}
              onChange={(e) => setServerParams({ ...serverParams, url: e.target.value })}
              placeholder="E.g., http://localhost:8080"
            />
          </InputWithTooltip>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <Button 
            onClick={() => {
              setIsAddingServer(false);
              setEditingIndex(null);
              setServerParams({
                serverId: "",
                serverType: "stdio",
                command: "",
                args: "",
              });
            }}
          >
            Cancel
          </Button>
          <Button type="primary" onClick={handleAddServer}>
            {editingIndex !== null ? "Update" : "Add"} Server
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <DetailGroup title="Basic Information">
        <div className="space-y-4">
          <InputWithTooltip 
            label="Name" 
            tooltip="Name of this workbench"
          >
            <Input
              value={component.label || ""}
              onChange={(e) => handleComponentUpdate({ label: e.target.value })}
              placeholder="Workbench name"
            />
          </InputWithTooltip>

          <InputWithTooltip 
            label="Description" 
            tooltip="Description of this workbench"
          >
            <TextArea
              value={component.description || ""}
              onChange={(e) => handleComponentUpdate({ description: e.target.value })}
              placeholder="A brief description of this workbench"
              rows={4}
            />
          </InputWithTooltip>
        </div>
      </DetailGroup>

      <DetailGroup title="Server Configuration">
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-medium text-primary">MCP Servers</h3>
            {!isAddingServer && (
              <Button
                type="primary"
                size="small"
                icon={<PlusCircle className="w-4 h-4 mr-1" />}
                onClick={() => {
                  setIsAddingServer(true);
                  setEditingIndex(null);
                  setServerParams({
                    serverId: "",
                    serverType: "stdio",
                    command: "",
                    args: "",
                  });
                }}
              >
                Add Server
              </Button>
            )}
          </div>

          {isAddingServer && renderServerForm()}

          {!isAddingServer && component.config.server_params_list?.length > 0 && (
            <List
              bordered
              dataSource={component.config.server_params_list}
              renderItem={(server, index) => {
                const isStdio = "command" in server.server_params;
                return (
                  <List.Item
                    key={index}
                    actions={[
                      <Button
                        key="edit"
                        type="text"
                        icon={<Edit className="w-4 h-4" />}
                        onClick={() => handleEditServer(index)}
                      />,
                      <Button
                        key="delete"
                        type="text"
                        danger
                        icon={<MinusCircle className="w-4 h-4" />}
                        onClick={() => handleRemoveServer(index)}
                      />,
                    ]}
                  >
                    <div>
                      <div className="font-medium">{server.server_id}</div>
                      <div className="text-sm text-secondary">
                        {isStdio ? (
                          <>
                            {server.server_params.command}{" "}
                            {Array.isArray(server.server_params.args)
                              ? server.server_params.args.join(" ")
                              : ""}
                          </>
                        ) : (
                          server.server_params.url
                        )}
                      </div>
                    </div>
                  </List.Item>
                );
              }}
            />
          )}

          {!isAddingServer && (!component.config.server_params_list || component.config.server_params_list.length === 0) && (
            <div className="text-sm text-secondary text-center bg-secondary/50 p-4 rounded-md">
              No servers configured yet. Add a server to get started.
            </div>
          )}
        </div>
      </DetailGroup>
    </div>
  );
};

export default WorkbenchFields;
