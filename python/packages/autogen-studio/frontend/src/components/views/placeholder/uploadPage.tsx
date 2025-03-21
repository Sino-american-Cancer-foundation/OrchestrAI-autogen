import React, { useCallback, useContext, useEffect, useState } from "react";
import { Form, Input, Button, Checkbox, message } from "antd";
import { Gallery, ToolConfig, Component } from "../../types/datamodel";
import { appContext } from "../../../hooks/provider";
import { galleryAPI } from "../gallery/api";
import Editor from "@monaco-editor/react";

export interface ToolComponentProps {
    initialTool?: ToolConfig;
    onSave: (updates: Partial<Gallery>) => Promise<void>;
    onCancel?: () => void;
}

const defaultToolConfig: ToolConfig = {
    source_code: "",
    name: "New Tool",
    description: "A new tool",
    global_imports: [],
    has_cancellation_support: false,
};

const ToolComponent: React.FC<ToolComponentProps> = ({
    initialTool,
    onSave,
    onCancel,
}) => {
    const { user } = useContext(appContext);
    const [messageApi, contextHolder] = message.useMessage();
    const [currentGallery, setCurrentGallery] = useState<Gallery | null>(null);
    const [sourceCode, setSourceCode] = useState(
        initialTool?.source_code || ""
    );

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

    const [form] = Form.useForm<
        ToolConfig & { global_imports: string | string[] }
    >();
    const initialValues = initialTool || defaultToolConfig;

    const handleFinish = async (values: any) => {
        if (!currentGallery) return;
        const updatedTool: ToolConfig = { ...values, source_code: sourceCode };

        const currentTools = currentGallery.config.components.tools || [];
        const newToolComponent: Component<ToolConfig> = {
            provider: "new",
            component_type: "tool",
            config: updatedTool,
            label: updatedTool.name,
        };

        const updatedTools = [...currentTools, newToolComponent];

        const sanitizedUpdates: Partial<Gallery> = {
            config: {
                ...currentGallery.config,
                components: {
                    ...currentGallery.config.components,
                    tools: updatedTools,
                },
            },
            created_at: undefined,
            updated_at: undefined,
        };

        try {
            await onSave(sanitizedUpdates);
        } catch (error) {
            console.error("Error saving tool:", error);
            message.error("Failed to save tool");
        }
    };

    return (
        <>
            {contextHolder}
            <Form
                form={form}
                layout="vertical"
                initialValues={initialValues}
                onFinish={handleFinish}
            >
                <Form.Item
                    label="Tool Name"
                    name="name"
                    rules={[
                        {
                            required: true,
                            message: "Please input the tool name",
                        },
                    ]}
                >
                    <Input placeholder="Enter tool name" />
                </Form.Item>

                <Form.Item
                    label="Description"
                    name="description"
                    rules={[
                        {
                            required: true,
                            message: "Please input a description",
                        },
                    ]}
                >
                    <Input.TextArea
                        placeholder="Enter tool description"
                        rows={3}
                    />
                </Form.Item>

                {/* Monaco Editor for Source Code */}
                <Form.Item label="Source Code">
                    <Editor
                        height="300px"
                        defaultLanguage="javascript"
                        defaultValue={sourceCode}
                        theme="vs-dark"
                        onChange={(value) => setSourceCode(value || "")}
                        options={{
                            minimap: { enabled: false },
                            fontSize: 14,
                        }}
                    />
                </Form.Item>

                <Form.Item label="Global Imports" name="global_imports">
                    <Input.TextArea
                        placeholder="Enter global imports, separated by commas"
                        rows={2}
                    />
                </Form.Item>

                <Form.Item
                    name="has_cancellation_support"
                    valuePropName="checked"
                >
                    <Checkbox>Has Cancellation Support</Checkbox>
                </Form.Item>

                <Form.Item>
                    <Button
                        type="primary"
                        htmlType="submit"
                        style={{ marginRight: 8 }}
                    >
                        Save Tool
                    </Button>
                    {onCancel && (
                        <Button htmlType="button" onClick={onCancel}>
                            Cancel
                        </Button>
                    )}
                </Form.Item>
            </Form>
        </>
    );
};

export default ToolComponent;
