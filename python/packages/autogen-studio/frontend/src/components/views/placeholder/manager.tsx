import React, { useContext, useEffect, useState } from "react";
import { Layout } from "antd";
import { appContext } from "../../../hooks/provider";
import { message, Modal } from "antd";
import ProviderSidebar from "./sidebar";
import Sider from "antd/es/layout/Sider";
import { Content } from "antd/es/layout/layout";
import UploadPage from "./uploadPage";
import ItemsPage from "./itemsPage";
import AgentPage from "./agentPage";
import { Gallery } from "../../types/datamodel";
import { galleryAPI } from "../gallery/api";
import UploadTeamPage from "./uploadTeamPage";
import UploadAgentPage from "./uploadAgentPage";

const PlaceholderManager: React.FC = () => {
    const { user } = useContext(appContext);
    const [messageApi, contextHolder] = message.useMessage();

    // copied from AutoGen's gallery manager
    const handleUpdateGallery = async (updates: Partial<Gallery>) => {
        if (!user?.email) return;

        try {
            const sanitizedUpdates = {
                ...updates,
                created_at: undefined,
                updated_at: undefined,
            };

            const data = galleryAPI.listGalleries(user.email);
            console.log("DATA:", data);
            const updatedGallery = await galleryAPI.updateGallery(
                1, // Default to default-gallery. i looked this up and hard-coded it from the api, probably should be improved
                sanitizedUpdates,
                user.email
            );

            messageApi.success("Gallery updated successfully");
        } catch (error) {
            console.error("Error updating gallery:", error);
            messageApi.error("Failed to update gallery");
        }
    };

    const [selectedKey, setSelectedKey] = useState<string>("agentUpload");

    const renderContent = () => {
        switch (selectedKey) {
            case "providerUpload":
                return <UploadPage onSave={handleUpdateGallery} />;
            case "currentItems":
                return <ItemsPage />;
            case "chatbot":
                return <AgentPage />;

            case "teamUpload":
                return (
                    <UploadTeamPage
                        selectedKey={selectedKey}
                        onSelect={setSelectedKey}
                    />
                );

            case "agentUpload":
                return <UploadAgentPage />;
            default:
                return null;
        }
    };

    return (
        <div className="grid grid-cols-12 divide-x h-full divide-secondary">
            <div className="col-span-2 pr-2">
                <ProviderSidebar
                    selectedKey={selectedKey}
                    onSelect={setSelectedKey}
                />{" "}
            </div>

            <div className="col-span-10 flex flex-col h-full">
                {renderContent()}{" "}
            </div>
        </div>
    );
};

export default PlaceholderManager;
