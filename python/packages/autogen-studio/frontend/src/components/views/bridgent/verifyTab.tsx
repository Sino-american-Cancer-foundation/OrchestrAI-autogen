import React, { useState } from "react";
import {
    aesDecryptCurve25519Data,
    readDecodeBufferIntoJson,
} from "./cryptography/decrypt";
import { Button, Card, Col, Divider, Input, Row } from "antd";
interface VerifyTabProps {}
const VerifyTab: React.FC<VerifyTabProps> = () => {
    const [formData, setFormData] = useState({
        targetContentId: "",
    });
    const [encryptedData, setEncryptedData] = useState("");
    const [decryptedData, setDecryptedData] = useState("");
    const [isLoading, setIsLoading] = useState(false);

    const searchTargetContentId = async (targetContentId: string) => {
        const baseUrl = process.env.GATSBY_FIREFLY_API_URL;
        const url = new URL(
            `${baseUrl}/api/v1/data/${targetContentId.trim()}/blob`
        );
        console.log("URL: ", url);
        const response = await fetch(url.toString(), {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }

        const blob = await response.blob();
        console.log("Blob received:", blob);
        const textData = await blob.text();
        console.log("Text Data:", textData);
        const data = JSON.parse(textData);
        console.log("Parsed Data:", data);

        setEncryptedData(JSON.stringify(data, null, 2));

        const {
            encrypted_aes_key_b64,
            encrypted_data_b64,
            curve25519_nonce_b64,
            ephemeral_public_key_b64,
            aes_iv_b64,
        } = data;

        const data_bytes = await aesDecryptCurve25519Data(
            encrypted_aes_key_b64,
            encrypted_data_b64,
            aes_iv_b64,
            curve25519_nonce_b64,
            ephemeral_public_key_b64
        );
        const data_json = readDecodeBufferIntoJson(data_bytes);

        setDecryptedData(JSON.stringify(data_json, null, 2));
    };

    const handleChange = (name: string, value: string | string[]) => {
        setFormData({ ...formData, [name]: value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            await searchTargetContentId(formData.targetContentId);
        } catch (error) {
            console.error("Error searching target contnent id...", error);
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
                    <div className="text-xl">Search Target Content Id</div>
                    <div>
                        <label className="block mb-1 text-sm font-medium">
                            Target Content ID
                        </label>
                        <Input
                            placeholder="00000000-0000-0000-0000-000000000000"
                            value={formData.targetContentId}
                            onChange={(e) =>
                                handleChange("targetContentId", e.target.value)
                            }
                        />
                    </div>

                    <Button
                        type="primary"
                        htmlType="submit"
                        className="w-full"
                        loading={isLoading}
                    >
                        Search
                    </Button>
                </div>

                <Divider />

                <div className="flex-1 overflow-y-auto space-y-4">
                    <div className="tracking-wide uppercase text-xl">
                        Returned Content
                    </div>

                    <Card title="Encrypted Data" bordered>
                        <pre
                            style={{
                                maxHeight: "300px",
                                overflow: "auto",
                                whiteSpace: "pre-wrap",
                                wordWrap: "break-word",
                            }}
                        >
                            {encryptedData}
                        </pre>
                    </Card>
                    <Card title="Decrypted Data" bordered>
                        <pre
                            style={{
                                maxHeight: "300px",
                                overflow: "auto",
                                whiteSpace: "pre-wrap",
                                wordWrap: "break-word",
                            }}
                        >
                            {decryptedData}
                        </pre>
                    </Card>
                </div>
            </form>
        </>
    );
};
export default VerifyTab;
