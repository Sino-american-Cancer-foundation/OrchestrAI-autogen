import React, { useState } from "react";
import { Input, Button, Checkbox, Divider, Upload, Tabs } from "antd";
import type { UploadProps } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { FunctionFlags } from "./types";
import { encryptAndUploadToFireFly, invokeFireFlyAPI } from "./upload";

const functionKeys = Object.keys(FunctionFlags).filter((key) =>
    isNaN(Number(key))
);

const functionOptions = functionKeys.map((key, index) => ({
    label: key.replace(/([A-Z])/g, " $1").trim(),
    value: String(FunctionFlags[key as keyof typeof FunctionFlags]),
    disabled: index === 0, // first one should always be active lol
}));

interface UploadTabProps {}
const UploadTab: React.FC<UploadTabProps> = () => {
    const [formData, setFormData] = useState({
        fullName: "John Doe",
        functions: [functionOptions[0].value] as string[],
        file: null as File | null,
    });
    const [isLoading, setIsLoading] = useState(false);

    const handleChange = (name: string, value: string | string[]) => {
        setFormData({ ...formData, [name]: value });
    };

    const beforeUpload = (file: File) => {
        setFormData({ ...formData, file });
        return false;
    };

    const uploadProps: UploadProps = {
        name: "file",
        multiple: false,
        beforeUpload,
        maxCount: 1,
        onDrop(e) {
            console.log("Dropped files", e.dataTransfer.files);
        },
        listType: "picture",
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);

        try {
            const userAddress = process.env.GATSBY_FIREFLY_TEST_USER_ADDRESS;

            if (!userAddress) {
                throw new Error(
                    "Failed to find user address when submitting..."
                );
            }

            if (!formData.file) {
                throw new Error("Failed to find image when submitting...");
            }

            const { id, computedHash } = await encryptAndUploadToFireFly(
                formData.file,
                formData.fullName
            );
            await invokeFireFlyAPI(
                id,
                computedHash,
                formData.functions,
                userAddress
            );
        } catch (error) {
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <form
                onSubmit={handleSubmit}
                className="flex flex-col p-2 pr-4 mt-2"
            >
                <div className="flex-1 overflow-y-auto space-y-4">
                    <div className="text-xl">Upload Dummy Data</div>
                    <div className="space-y-2">
                        <div className="tracking-tight uppercase font-semibold font-normal">
                            User Information
                        </div>
                        <div className="space-y-4">
                            <div>
                                <label className="block mb-1 text-sm font-medium">
                                    Full Name
                                </label>
                                <Input
                                    placeholder="Full Name (First + Last)"
                                    value={formData.fullName}
                                    onChange={(e) =>
                                        handleChange("fullName", e.target.value)
                                    }
                                />
                            </div>
                        </div>
                    </div>
                    <Divider />
                    <div>
                        <div className="tracking-tight uppercase font-semibold font-normal mb-2">
                            Image Upload & Preview
                        </div>
                        <Upload.Dragger {...uploadProps}>
                            <div className="flex flex-col space-y-2 items-center">
                                <InboxOutlined className="text-4xl text-gray-400" />
                                <div className="flex flex-col space-y-0">
                                    <p className="text-md tracking-wide">
                                        Click or Drag File(s)
                                    </p>
                                </div>
                            </div>
                        </Upload.Dragger>
                    </div>
                    <Divider />
                    <div>
                        <div className="tracking-tight uppercase font-semibold font-normal mb-2">
                            Select Functions
                        </div>
                        <Checkbox.Group
                            options={functionOptions}
                            value={formData.functions}
                            onChange={(checkedValues) =>
                                handleChange(
                                    "functions",
                                    checkedValues as string[]
                                )
                            }
                            className="flex flex-col gap-2"
                        />
                    </div>
                </div>
                <Divider />
                <Button
                    type="primary"
                    htmlType="submit"
                    className="w-full"
                    loading={isLoading}
                >
                    Submit
                </Button>
            </form>
        </>
    );
};
export default UploadTab;
