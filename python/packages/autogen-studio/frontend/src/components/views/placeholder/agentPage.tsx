import React, { useState, useEffect, useRef } from "react";
import { Input, Button, List, Divider } from "antd";
import { ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
const AgentPage: React.FC = () => {
    interface ChatMessage {
        sender:
            | "user"
            | "summary_assistant"
            | "task_agent"
            | "error"
            | "bot"
            | "system";
        text: string;
    }

    interface ToolInfo {
        label: string;
        component_type: string;
        version: number;
        description: string;
    }

    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [tools, setTools] = useState<ToolInfo[]>([]);
    const [inputValue, setInputValue] = useState<string>("");
    const [inputDisabled, setInputDisabled] = useState<boolean>(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const lastMessageRef = useRef<ChatMessage | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        const fetchTools = async () => {
            try {
                const res = await fetch("http://localhost:4000/dump-tools");
                if (res.ok) {
                    const data = await res.json();
                    setTools(data);
                }
            } catch (err) {
                console.error("Error fetching tools", err);
            }
        };
        fetchTools();
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    useEffect(() => {
        const ws = new WebSocket("ws://localhost:4000/ws/chat");
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("Connected to WebSocket");
            setInputDisabled(false);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log("Received:", data);

                let content =
                    typeof data.content === "string"
                        ? data.content
                        : JSON.stringify(data.content);

                if (data.type === "UserInputRequestedEvent") {
                    if (data.source === "user") {
                        setInputDisabled(false);
                    }
                    return;
                } else if (data.type === "error") {
                    addMessage({ sender: "error", text: content });
                    setInputDisabled(false);
                } else if (data.source === "user") {
                    if (
                        lastMessageRef.current &&
                        lastMessageRef.current.sender === "user" &&
                        lastMessageRef.current.text === content
                    ) {
                        return;
                    }
                    addMessage({ sender: "user", text: content });
                } else if (data.source === "summary_assistant") {
                    addMessage({
                        sender: "summary_assistant",
                        text: content,
                    });
                } else if (data.source === "task_agent") {
                    try {
                        const parsed = JSON.parse(content);
                        if (
                            parsed &&
                            parsed.data &&
                            parsed.data.task_result &&
                            Array.isArray(parsed.data.task_result.messages)
                        ) {
                            const messagesArray =
                                parsed.data.task_result.messages;
                            const lastTwo = messagesArray.slice(-2);
                            const formatted = JSON.stringify(lastTwo, null, 2);
                            addMessage({
                                sender: "task_agent",
                                text: formatted,
                            });
                        } else {
                            addMessage({
                                sender: "task_agent",
                                text: JSON.stringify(parsed, null, 2),
                            });
                        }
                    } catch (err) {
                        addMessage({
                            sender: "task_agent",
                            text: content,
                        });
                    }
                }
            } catch (err) {
                console.error("Error parsing message:", err);
            }
        };

        ws.onerror = () => {
            addMessage({
                sender: "error",
                text: "WebSocket error occurred. Please refresh the page.",
            });
            setInputDisabled(false);
        };

        ws.onclose = () => {
            addMessage({
                sender: "system",
                text: "Connection closed. Please refresh the page.",
            });
            setInputDisabled(true);
        };

        return () => {
            ws.close();
        };
    }, []);

    const addMessage = (msg: ChatMessage) => {
        setMessages((prev) => {
            const newMessages = [...prev, msg];
            lastMessageRef.current = msg;
            return newMessages;
        });
    };

    const handleSend = () => {
        if (!inputValue.trim() || inputDisabled) return;
        const userMsg = inputValue.trim();
        setInputValue("");
        setInputDisabled(true);
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(
                JSON.stringify({ content: userMsg, source: "user" })
            );
        }
    };

    return (
        <>
            <div className="flex items-center gap-2 text-sm p-2 px-4">
                <span className="text-primary font-medium">
                    Provider Placeholders
                </span>
                <ChevronRight className="w-4 h-4 text-secondary" />
                <span className="text-secondary">Agent Chat</span>
            </div>
            <div className="p-4 flex flex-col space-y-1 ">
                <div className="text-3xl font-bold ">Demo Chat</div>
                <div className="text-md font-secondary">
                    This page connects to the locally run mcp_tools file as a
                    demonstration before this functionality is transitioned into
                    SSE events.
                </div>
            </div>
            <div className="px-2 flex h-full">
                <div
                    style={{ width: 1200, maxWidth: "100%" }}
                    className="flex flex-col h-full border border-secondary p-4 rounded"
                >
                    <div className="h-[32rem] overflow-y-auto flex w-full flex-col">
                        <List
                            dataSource={messages}
                            renderItem={(msg, index) => (
                                <List.Item
                                    key={index}
                                    style={{
                                        justifyContent:
                                            msg.sender === "user"
                                                ? "flex-end"
                                                : "flex-start",
                                        padding: 0,
                                    }}
                                >
                                    {msg.sender === "user" ? (
                                        <div
                                            className="flex flex-col mb-4"
                                            style={{ maxWidth: "70%" }}
                                        >
                                            <div className="mb-1 text-xs mt-4 font-semibold text-gray-600 text-right">
                                                {msg.sender.toUpperCase()}
                                            </div>
                                            <div
                                                className="truncate w-72 text-wrap"
                                                style={{
                                                    backgroundColor: "#1890ff",
                                                    color: "#fff",
                                                    padding: "8px 12px",
                                                    borderRadius: "4px",
                                                }}
                                            >
                                                {msg.text}
                                            </div>
                                        </div>
                                    ) : (
                                        <div style={{ maxWidth: "70%" }}>
                                            <div className="mb-1 mt-4 text-xs font-semibold text-gray-600">
                                                {msg.sender.toUpperCase()}
                                            </div>
                                            {msg.sender ===
                                            "summary_assistant" ? (
                                                <div
                                                    className="w-72 mb-4 text-wrap"
                                                    style={{
                                                        backgroundColor:
                                                            "#e6f7ff",
                                                        color: "#000",
                                                        padding: "8px 12px",
                                                        borderRadius: "4px",
                                                    }}
                                                >
                                                    <ReactMarkdown>
                                                        {msg.text}
                                                    </ReactMarkdown>
                                                </div>
                                            ) : msg.sender === "task_agent" ? (
                                                <pre className="w-72 mb-4 p-3 text-xs font-mono bg-green-100 text-green-800 border border-secondary rounded overflow-x-auto text-wrap truncate">
                                                    {msg.text}
                                                </pre>
                                            ) : (
                                                <div
                                                    className="truncate w-72 mb-4 text-wrap"
                                                    style={{
                                                        backgroundColor:
                                                            msg.sender === "bot"
                                                                ? "#f0f0f0"
                                                                : msg.sender ===
                                                                  "error"
                                                                ? "#fff1f0"
                                                                : "#e6f7ff",
                                                        color: "#000",
                                                        padding: "8px 12px",
                                                        borderRadius: "4px",
                                                    }}
                                                >
                                                    {msg.text}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </List.Item>
                            )}
                        />

                        <div ref={messagesEndRef} />
                    </div>
                    <Divider />
                    <div className="flex flex-col">
                        {inputDisabled && (
                            <div className="mt-2 text-xs font-semibold text-secondary uppercase animate-pulse">
                                thinking...
                            </div>
                        )}

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

                <div
                    title="MCP Tools"
                    style={{ width: 300, maxWidth: "100%" }}
                    className="ml-4 flex flex-col h-full border border-secondary p-4 rounded"
                >
                    <h3 className="text-lg font-bold mb-2">Local MCP Tools</h3>
                    <List
                        dataSource={tools}
                        renderItem={(tool, index) => (
                            <List.Item key={index}>
                                <div>
                                    <div className="font-medium">
                                        {tool.label}
                                    </div>
                                    <div className="text-sm text-gray-600">
                                        {tool.description}
                                    </div>
                                </div>
                            </List.Item>
                        )}
                    />
                </div>
            </div>
        </>
    );
};

export default AgentPage;
