import React, { useEffect, useRef, useState } from "react";
import { Button, Divider, Input, List, Upload, notification } from "antd";
import type { UploadFile } from "antd/es/upload/interface";
import { CheckCircle, Loader2, Radio, XCircle } from "lucide-react";
import { Button as HeadlessButton } from "@headlessui/react";
interface ChatMessage {
    source: "System" | "User" | "Deployer" | "Executor";
    text: string;
}

const UploadAgentPage: React.FC = () => {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [inputValue, setInputValue] = useState<string>("");
    const [inputDisabled, setInputDisabled] = useState<boolean>(false);
    const [teamFile, setTeamFile] = useState<UploadFile | null>(null);
    const messagesContainerRef = useRef<HTMLDivElement | null>(null);

    const [wsStatus, setWsStatus] = useState<
        "connecting" | "connected" | "disconnected"
    >("disconnected");
    const wsRef = useRef<WebSocket | null>(null);

    const connectWebSocket = () => {
        const BASE_URL = "ws://localhost:9001/ws";

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.close();
        }

        setWsStatus("connecting");
        const ws = new WebSocket(BASE_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            if (wsRef.current === ws) {
                console.log(`Connected to WebSocket at: ${BASE_URL}`);
                setWsStatus("connected");
            }
        };

        ws.onmessage = (event) => {
            try {
                const { text, source } = (
                    typeof event.data === "string"
                        ? JSON.parse(event.data)
                        : event.data
                ) as ChatMessage;

                setMessages((prevMessages) => {
                    if (
                        source === "User" &&
                        prevMessages.length > 0 &&
                        prevMessages[prevMessages.length - 1].source ===
                            "User" &&
                        prevMessages[prevMessages.length - 1].text === text
                    ) {
                        return prevMessages;
                    }
                    return [...prevMessages, { source, text }];
                });
            } catch (err) {
                console.error("Error parsing message:", err);
            }
        };

        ws.onerror = (error) => {
            console.error("WebSocket error:", error);
        };

        ws.onclose = () => {
            if (wsRef.current === ws) {
                setWsStatus("disconnected");
                console.log("WebSocket connection closed");
            }
        };
    };

    const getMessageStyle = (source: string): React.CSSProperties => {
        switch (source) {
            case "User":
                return {
                    backgroundColor: "#e6f7ff",
                    color: "#000",
                    padding: "8px",
                    borderRadius: "4px",
                    maxWidth: "60%",
                    alignSelf: "flex-end",
                    margin: "4px 0",
                };
            case "System":
                return {
                    backgroundColor: "#f0f0f0",
                    color: "#000",
                    padding: "8px",
                    borderRadius: "4px",
                    maxWidth: "60%",
                    alignSelf: "flex-start",
                    margin: "4px 0",
                };
            case "Deployer":
            case "Executor":
                return {
                    backgroundColor: "#fff7e6",
                    color: "#000",
                    padding: "8px",
                    borderRadius: "4px",
                    maxWidth: "60%",
                    alignSelf: "flex-start",
                    margin: "4px 0",
                };
            default:
                return {
                    backgroundColor: "#f0f0f0",
                    color: "#000",
                    padding: "8px",
                    borderRadius: "4px",
                    maxWidth: "60%",
                    alignSelf: "flex-start",
                    margin: "4px 0",
                };
        }
    };

    useEffect(() => {
        connectWebSocket();

        return () => {
            wsRef.current?.close();
            console.log("WebSocket connection closed from client side");
        };
    }, []);

    useEffect(() => {
        if (messagesContainerRef.current) {
            messagesContainerRef.current.scrollTop =
                messagesContainerRef.current.scrollHeight;
        }
    }, [messages]);

    const uploadTeamFile = async (file: UploadFile): Promise<string | null> => {
        try {
            let FIREFLY_BASE_URL;
            // FIREFLY_BASE_URL = "http://localhost:5000";
            FIREFLY_BASE_URL = "https://api.aidtech.ai";
            const FIREFLY_URL = `${FIREFLY_BASE_URL}/api/v1`;

            const fileObj: Blob =
                file.originFileObj ?? (file as unknown as Blob);
            if (!(fileObj instanceof Blob)) {
                throw new Error("File content is unavailable");
            }

            const arrayBuffer = await fileObj.arrayBuffer();
            if (!arrayBuffer) {
                throw new Error("File content is unavailable");
            }
            const blob = new Blob([arrayBuffer], { type: "application/zip" });

            const formData = new FormData();
            formData.append("file", blob, file.name);

            const response = await fetch(`${FIREFLY_URL}/data`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                throw new Error("File upload failed");
            }
            const data = await response.json();
            console.log("Upload successful:", data);
            return data.id;
        } catch (error) {
            console.error("Error uploading file:", error);
            return null;
        }
    };

    const handleSend = async () => {
        if (!inputValue.trim() || inputDisabled) return;
        const userMsg = inputValue.trim();
        setInputValue("");

        let teamId: string | null = "";
        if (teamFile) {
            try {
                setInputDisabled(true);
                teamId = await uploadTeamFile(teamFile);

                await new Promise((resolve) => setTimeout(resolve, 1000));
                if (!teamId) return;
                notification.success({
                    message: "Team file successfully uploaded",
                    description: `Received team id: ${teamId}`,
                });
                setTeamFile(null);
            } catch (err) {
                notification.error({
                    message: "Error uploading team file",
                });
                setInputDisabled(false);
                return;
            }
            setInputDisabled(false);
        }

        const messageToSend = teamId
            ? `${userMsg}, team json id: ${teamId}`
            : userMsg;

        // The distributed runtime actually returns the same message back to us lol, so no need to repeat the same message
        // setMessages((prevMessages) => [
        //     ...prevMessages,
        //     { source: "User", text: messageToSend },
        // ]);

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(messageToSend);
        }
    };

    return (
        <>
            <div className="flex flex-row items-center justify-between p-2">
                <div className="flex flex-col">
                    <div className="text-primary">
                        Chatbot to Upload an Agentic Process as a Smart Contract
                    </div>
                    <div className="text-secondary text-xs uppercase">
                        Requires: api-name, function-name(s), cost(s), and team
                        json.
                    </div>
                </div>

                <button
                    onClick={connectWebSocket}
                    disabled={wsStatus === "connected"}
                    className={`
                        inline-flex items-center justify-center
                        px-4 py-2 rounded-sm
                        rounded-lg text-sm border
                        focus:outline-none focus:ring-2 focus:ring-offset-2
                        disabled:cursor-not-allowed
                        transition-colors duration-200 hover:text-white hover

                        ${
                            wsStatus === "connected"
                                ? "border-green-500 text-green-500 hover:text-green-500"
                                : ""
                        }
                        ${
                            wsStatus === "connecting"
                                ? "border-yellow-500 text-yellow-500 hover:bg-yellow-600 focus:ring-yellow-300"
                                : ""
                        }
                        ${
                            wsStatus === "disconnected"
                                ? "border-red-500 text-red-500 hover:bg-red-600 focus:ring-red-300"
                                : ""
                        }
                    `}
                >
                    <span
                        className={`
      inline-block w-2 h-2 rounded-full mr-2
      ${
          wsStatus === "connected"
              ? "bg-green-500"
              : wsStatus === "connecting"
              ? "bg-yellow-500 animate-pulse"
              : "bg-red-500"
      }
    `}
                    />

                    {wsStatus === "connected"
                        ? "Connected"
                        : wsStatus === "connecting"
                        ? "Connecting..."
                        : "Reconnect..."}
                </button>
            </div>
            <div className="px-2 flex h-full">
                <div
                    style={{ width: 1200, maxWidth: "100%" }}
                    className="flex flex-col h-full border border-secondary p-4 rounded"
                >
                    <div
                        ref={messagesContainerRef}
                        className="h-[32rem] overflow-y-auto flex w-full flex-col"
                    >
                        <List
                            dataSource={messages}
                            renderItem={(msg, index) => (
                                <List.Item
                                    key={index}
                                    style={{
                                        display: "flex",
                                        justifyContent:
                                            msg.source === "User"
                                                ? "flex-end"
                                                : "flex-start",
                                        padding: 0,
                                        border: "none",
                                        background: "none",
                                    }}
                                >
                                    <div style={getMessageStyle(msg.source)}>
                                        {msg.text}
                                    </div>
                                </List.Item>
                            )}
                        />
                    </div>
                    <Divider />
                    <div className="flex flex-col">
                        {inputDisabled && (
                            <div className="mt-2 text-xs font-semibold text-secondary uppercase animate-pulse">
                                thinking...
                            </div>
                        )}
                        <Upload
                            accept=".json"
                            beforeUpload={(file) => {
                                if (
                                    file.type !== "application/json" &&
                                    !file.name.endsWith(".json")
                                ) {
                                    notification.error({
                                        message: "Invalid file type",
                                        description:
                                            "Only JSON files are allowed.",
                                    });
                                    return Upload.LIST_IGNORE;
                                }
                                setTeamFile(file);
                                notification.info({
                                    message:
                                        "Selected JSON will be uploaded and used as the team",
                                });
                                return false;
                            }}
                            fileList={teamFile ? [teamFile] : []}
                            onRemove={() => setTeamFile(null)}
                        >
                            <Button style={{ marginBottom: "16px" }}>
                                Upload JSON Team File
                            </Button>
                        </Upload>
                        <div className="flex">
                            <Input
                                placeholder="Type your message..."
                                value={inputValue}
                                disabled={inputDisabled}
                                onChange={(e) => setInputValue(e.target.value)}
                                onPressEnter={handleSend}
                            />
                            <Button
                                type="primary"
                                onClick={handleSend}
                                disabled={inputDisabled}
                                style={{ marginLeft: "8px" }}
                            >
                                Send
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};

export default UploadAgentPage;
