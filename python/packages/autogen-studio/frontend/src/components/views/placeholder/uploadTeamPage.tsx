import { ChevronRight } from "lucide-react";
import React, {
    useState,
    useRef,
    useCallback,
    useContext,
    useEffect,
} from "react";
import {
    Upload,
    Button,
    message,
    Input,
    Card,
    InputNumber,
    Divider,
} from "antd";
import type { UploadProps } from "antd";
import JSZip from "jszip";
import {
    Component,
    ComponentConfig,
    ComponentTypes,
    Gallery,
} from "../../types/datamodel";
import { appContext } from "../../../hooks/provider";
import { galleryAPI } from "../gallery/api";

interface UploadTeamPageProps {
    selectedKey: string;
    onSelect: (key: string) => void;
}

interface ApiConfig {
    admin_address: string;
    agent_subscription: string;
    contract_address: string;
    firefly_ws_url: string;
    firefly_api_url: string;
    listener_id: string;
}
type CategoryKey = `${ComponentTypes}s`;

const UploadTeamPage: React.FC<UploadTeamPageProps> = ({
    selectedKey,
    onSelect,
}) => {
    const [jsonData, setJsonData] = useState<any>(null);
    const [jsonString, setJsonString] = useState<string>("");
    const [toolsData, setToolsData] = useState<any[]>([]);
    const [toolCosts, setToolCosts] = useState<number[]>([]);
    const [apiName, setApiName] = useState<string>("");
    const [submitted, setSubmitted] = useState(false);
    const [loading, setLoading] = useState<boolean>(false);

    // Default AutoGen gallery stuff
    const { user } = useContext(appContext);
    const [currentGallery, setCurrentGallery] = useState<Gallery>();
    const [messageApi, contextHolder] = message.useMessage();

    const fetchGalleries = useCallback(async () => {
        if (!user?.email) return;

        try {
            const data = await galleryAPI.listGalleries(user.email);
            if (!currentGallery && data.length > 0) {
                setCurrentGallery(data[0]);
            }
        } catch (error) {
            console.error("Error fetching galleries:", error);
            messageApi.error("Failed to fetch galleries");
        }
    }, [user?.email, currentGallery, messageApi]);

    useEffect(() => {
        fetchGalleries();
    }, [fetchGalleries]);

    const editorRef = useRef<any>(null);
    const defaultCost = 10;

    interface ExecutionWorkerConfig {
        OPENAI_API_KEY?: string; // THis shouldnt be here
        TASK_DESCRIPTION: string;
        FIREFLY_WEBSOCKET_URL: string;
        FIREFLY_AGENT_SUBSCRIPTION_NAME: string;
    }

    const handleFile = (file: File) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const text = e.target?.result as string;
                const parsed = JSON.parse(text);
                setJsonData(parsed);
                const formatted = JSON.stringify(parsed, null, 2);
                setJsonString(formatted);
                let toolsList: any[] = [];
                if (
                    parsed?.config?.participants &&
                    Array.isArray(parsed.config.participants)
                ) {
                    parsed.config.participants.forEach((participant: any) => {
                        if (
                            participant.config?.tools &&
                            Array.isArray(participant.config.tools)
                        ) {
                            toolsList = toolsList.concat(
                                participant.config.tools
                            );
                        }
                    });
                }
                if (toolsList.length > 0) {
                    setToolsData(toolsList);
                    setToolCosts(toolsList.map(() => defaultCost));
                    console.log("TOOLSLIST: ", toolsList);
                    const toolNames = toolsList
                        .map(
                            (item: any) =>
                                item.config?.tool?.name || item.config?.name
                        )
                        .filter(Boolean);
                    message.info(
                        `Found ${toolsList.length} tools: ${toolNames.join(
                            ", "
                        )}`
                    );

                    console.log("toolNames: ", toolNames);
                    if (editorRef.current) {
                        const index = formatted.indexOf('"tools":');
                        if (index !== -1) {
                            const beforeText = formatted.slice(0, index);
                            const lineNumber = beforeText.split("\n").length;
                            const lineHeight = 16;
                            editorRef.current.resizableTextArea.textArea.scrollTop =
                                (lineNumber - 1) * lineHeight;
                        }
                    }
                } else {
                    message.warning(
                        "No config.participants.tools array found in JSON."
                    );
                }
            } catch (error) {
                message.error("Invalid JSON file.");
            }
        };
        reader.readAsText(file);
        return false;
    };

    const uploadProps: UploadProps = {
        accept: ".json",
        beforeUpload: handleFile,
        showUploadList: false,
    };

    const handleUpdateGallery = async (updates: Partial<Gallery>) => {
        if (!user?.email || !currentGallery?.id) return;

        try {
            const sanitizedUpdates = {
                ...updates,
                created_at: undefined,
                updated_at: undefined,
            };
            const updatedGallery = await galleryAPI.updateGallery(
                currentGallery.id,
                sanitizedUpdates,
                user.email
            );

            // setCurrentGallery(updatedGallery);
            messageApi.success("Gallery updated successfully");
        } catch (error) {
            console.error("Error updating gallery:", error);
            messageApi.error("Failed to update gallery");
        }
    };

    const handleSubmit = async () => {
        setLoading(true);
        try {
            if (!jsonData || !apiName) {
                message.error("No JSON data or API name to submit.");
                return;
            }
            const functionNames: string[] = toolsData.map(
                (tool) => tool.config?.tool?.name || tool.config.name
            );

            const functionCosts: number[] = toolCosts.map((cost) => cost);

            console.log("Original JSON:", jsonData);
            console.log(
                "Extracted Tools with Cost:",
                functionNames,
                functionCosts
            );
            console.log("API name: ", apiName);

            message.success("Submission successful.");

            const url = "http://127.0.0.1:3000/processDeploy";

            try {
                const response = await fetch(url, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        functionNames,
                        functionCosts,
                        apiName,
                    }),
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }

                const fileBlob = await response.blob();
                console.log("FULLREPSONSE: ", response);
                const headerData = response.headers.get("x-response-data");
                const agentString = response.headers.get("x-agent-string");
                if (!agentString) {
                    throw new Error("x-agent-string header missing");
                }
                const category = "agents" as CategoryKey; // hard-cdoed
                const components = currentGallery?.config.components[category]!;
                let newComponent: Component<ComponentConfig> = JSON.parse(
                    agentString
                ) as Component<ComponentConfig>;
                newComponent.label = `${apiName}_Agent`;
                const updateGallery = (
                    category: CategoryKey,
                    updater: (
                        components: Component<ComponentConfig>[]
                    ) => Component<ComponentConfig>[]
                ) => {
                    const updatedGallery = {
                        ...currentGallery,
                        config: {
                            ...currentGallery!.config,
                            components: {
                                ...currentGallery!.config.components,
                                [category]: updater(
                                    currentGallery!.config.components[category]
                                ),
                            },
                        },
                    };
                    handleUpdateGallery(updatedGallery);
                };

                updateGallery(category, (components) => {
                    const newComponents = [...components, newComponent];
                    return newComponents;
                });

                let additionalData = null;
                if (headerData) {
                    try {
                        additionalData = JSON.parse(headerData) as ApiConfig;
                    } catch (e) {
                        console.error(
                            "Error parsing x-response-data header:",
                            e
                        );
                    }
                }
                console.log("Additional Data:", additionalData);

                let envContent = "";
                if (additionalData) {
                    envContent += `ADMIN_ADDRESS=${additionalData.admin_address}\n`;
                    envContent += `AGENT_SUBSCRIPTION=${additionalData.agent_subscription}\n`;
                    envContent += `CONTRACT_ADDRESS=${additionalData.contract_address}\n`;
                    envContent += `FIREFLY_WS_URL=${additionalData.firefly_ws_url}\n`;
                    envContent += `FIREFLY_API_URL=${additionalData.firefly_api_url}\n`;
                    envContent += `LISTENER_ID=${additionalData.listener_id}\n`;
                }

                const executionWorkerResponse = await fetch(
                    "/downloads/execution-worker.py"
                );
                if (!executionWorkerResponse.ok) {
                    throw new Error("Failed to fetch execution-worker.py");
                }
                const executionWorkerContent =
                    await executionWorkerResponse.text();

                const teamHtmlResponse = await fetch("/downloads/team.txt");
                if (!teamHtmlResponse.ok) {
                    throw new Error("Failed to fetch team.txt");
                }
                const teamHtmlContent = await teamHtmlResponse.text();

                const teamPyResponse = await fetch("/downloads/team.py");
                if (!teamPyResponse.ok) {
                    throw new Error("Failed to fetch team.py");
                }
                const teamPyContent = await teamPyResponse.text();

                const zip = new JSZip();
                zip.file("config.env", envContent);
                const executionWorkerFolder = zip.folder("execution-worker");
                if (executionWorkerFolder) {
                    executionWorkerFolder.file(
                        "execution-worker.py",
                        executionWorkerContent
                    );
                    if (jsonData) {
                        const jsonBlob = new Blob(
                            [JSON.stringify(jsonData, null, 2)],
                            { type: "application/json" }
                        );
                        executionWorkerFolder.file("team.json", jsonBlob);
                    }
                }

                const chatTeamFolder = zip.folder("chat-team");
                if (chatTeamFolder) {
                    chatTeamFolder.file("mcp_tools.py", fileBlob);
                    chatTeamFolder.file("team.html", teamHtmlContent);
                    chatTeamFolder.file("team.py", teamPyContent);
                }
                const zipBlob = await zip.generateAsync({ type: "blob" });
                const formData = new FormData();
                formData.append("file", zipBlob, "worker-mcptools.zip");

                try {
                    const response = await fetch(
                        "http://localhost:1234/deployClient",
                        {
                            method: "POST",
                            body: formData,
                        }
                    );

                    if (!response.ok) {
                        throw new Error(
                            `Server responded with ${response.status}`
                        );
                    }

                    const result = await response.json();
                    console.log("Deployment Response:", result);
                } catch (error) {
                    console.error("Fetch error:", error);
                }
                await new Promise<void>((resolve, reject) => {
                    setTimeout(() => {
                        resolve();
                    }, 5000);
                });
                message.success("Contract successfully uploaded!");
                onSelect("chatbot");
            } catch (error) {
                console.error("Fetch error:", error);
            }

            setSubmitted(true);
        } catch (error) {
            console.error("ERROR: ", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <div className="flex items-center gap-2 text-sm p-2 px-4">
                <span className="text-primary font-medium">
                    Provider Placeholders
                </span>
                <ChevronRight className="w-4 h-4 text-secondary" />
                <span className="text-secondary">Team Upload</span>
            </div>

            <div className="p-6 space-y-6">
                <div className="flex flex-col space-y-2">
                    <div className="text-secondary">API Name</div>
                    <Input
                        placeholder="Api Name"
                        className="border-secondary"
                        value={apiName}
                        onChange={(e) => setApiName(e.target.value)}
                    ></Input>
                </div>
            </div>

            <Upload {...uploadProps} className="px-2">
                <Button type="primary">Upload JSON File</Button>
            </Upload>
            <Divider />
            <div className="px-6 flex flex-col space-y-2">
                {jsonString && (
                    <Input.TextArea
                        ref={editorRef}
                        value={jsonString}
                        onChange={(e) => setJsonString(e.target.value)}
                        rows={15}
                        className="font-mono border-secondary"
                    />
                )}
                {toolsData.length > 0 && (
                    <div className="grid grid-cols-1 gap-4">
                        {toolsData.map((tool, index) => (
                            <div
                                key={index}
                                className="flex items-center justify-between bg-primary p-4 border border-secondary rounded"
                            >
                                <span className="font-medium">
                                    {tool.config?.tool?.name ||
                                        tool.config.name}
                                </span>
                                <InputNumber
                                    value={toolCosts[index]}
                                    onChange={(value) => {
                                        const newCosts = [...toolCosts];
                                        newCosts[index] = value || 0;
                                        setToolCosts(newCosts);
                                    }}
                                />
                            </div>
                        ))}
                    </div>
                )}
            </div>
            <div className="p-6">
                <Button
                    type="primary"
                    onClick={handleSubmit}
                    className="w-full"
                    loading={loading}
                >
                    Submit
                </Button>
            </div>
        </>
    );
};

export default UploadTeamPage;
