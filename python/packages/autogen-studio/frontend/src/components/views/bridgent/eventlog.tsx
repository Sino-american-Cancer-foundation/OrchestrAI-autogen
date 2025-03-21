import { List, Button } from "antd";
import { ChevronRight } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";

interface EventLogsProps {}

const EventLogs: React.FC<EventLogsProps> = () => {
    const [eventLogs, setEventLogs] = useState<any[]>([]);
    const [isConnecting, setIsConnecting] = useState<boolean>(false);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const mountedRef = useRef<boolean>(true);

    const connect = () => {
        if (!process.env.GATSBY_FIREFLY_WS_URL) {
            throw new Error(
                "Failed to find Gatsby FireFly URL when instantiating event log..."
            );
        }
        if (wsRef.current) return;

        setIsConnecting(true);
        const ws = new WebSocket(process.env.GATSBY_FIREFLY_WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("Connected to FireFly WebSocket...");
            setIsConnecting(false);
            if (!process.env.GATSBY_FIREFLY_TEST_USER_SUBSCRIPTION_NAME) {
                throw new Error(
                    "Failed to find Gatsby subscription name when opening WebSocket..."
                );
            }
            const startMessage = {
                type: "start",
                name: process.env.GATSBY_FIREFLY_TEST_USER_SUBSCRIPTION_NAME,
                namespace: "default",
                autoack: true,
            };
            ws.send(JSON.stringify(startMessage));
        };

        ws.onmessage = (message) => {
            const data = JSON.parse(message.data);
            console.log("Received WebSocket message: ", data);
            if (
                data.type === "blockchain_event_received" &&
                data.blockchainEvent
            ) {
                setEventLogs((prev) => {
                    const newEvent = {
                        name: data.blockchainEvent.name,
                        timestamp: data.blockchainEvent.timestamp,
                        ...data.blockchainEvent.output,
                    };
                    return [newEvent, ...prev];
                });
            }
        };

        ws.onerror = (error) => {
            console.error("WebSocket error: ", error);
        };

        ws.onclose = () => {
            console.log("Disconnected from FireFly WebSocket...");
            wsRef.current = null;
            if (mountedRef.current) {
                setIsConnecting(true);
                reconnectTimeoutRef.current = setTimeout(() => {
                    connect();
                }, 5000);
            }
        };
    };

    const disconnect = () => {
        if (wsRef.current) {
            wsRef.current.onopen = null;
            wsRef.current.onmessage = null;
            wsRef.current.onerror = null;
            wsRef.current.onclose = null;
            wsRef.current.close();
            wsRef.current = null;
        }
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
    };

    useEffect(() => {
        mountedRef.current = true;
        connect();

        return () => {
            mountedRef.current = false;
            disconnect();
        };
    }, []);

    return (
        <div className="h-full overflow-auto border-r border-secondary">
            <div className="h-full flex flex-col">
                <div className="flex items-center gap-2 text-sm p-2 px-4">
                    <span className="text-primary font-medium">
                        Demo Functionality
                    </span>
                    <ChevronRight className="w-4 h-4 text-secondary" />
                    <span className="text-secondary">Event Log</span>
                </div>
                <div className="w-full flex justify-between items-center pr-4">
                    <div className="text-3xl font-bold p-4">Latest Events</div>
                    <Button
                        type="default"
                        onClick={() => {
                            disconnect();
                            connect();
                        }}
                        loading={isConnecting}
                    >
                        {isConnecting ? "Connecting..." : "Reconnect"}
                    </Button>
                </div>
                <div className="border-t overflow-y-auto border-secondary">
                    <List
                        dataSource={eventLogs}
                        className="w-full flex-1 overflow-y-auto"
                        locale={{ emptyText: "No events available." }}
                        renderItem={(item, idx) => (
                            <List.Item
                                key={idx}
                                className={`${
                                    idx % 2 === 0 ? "bg-primary" : "bg-light"
                                } hover:bg-tertiary`}
                            >
                                <EventItem data={item} />
                            </List.Item>
                        )}
                    />
                </div>
            </div>
        </div>
    );
};

interface EventItemProps {
    data: Record<string, any>;
}

const EventItem: React.FC<EventItemProps> = ({ data }) => (
    <div className="w-full">
        {Object.entries(data).map(([key, value]) => (
            <div
                key={key}
                className="flex justify-between border-b border-secondary last:border-b-0 p-2 w-full"
            >
                <span className="font-medium text-primary">{key}:</span>
                <span className="text-secondary">{String(value)}</span>
            </div>
        ))}
    </div>
);

export default EventLogs;
