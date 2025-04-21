import { Menu } from "antd";
import {
    ListIcon,
    MessageCircleIcon,
    Upload,
    UploadIcon,
    ConstructionIcon,
} from "lucide-react";
import React from "react";

interface ProviderSidebarProps {
    selectedKey: string;
    onSelect: (key: string) => void;
}

const ProviderSidebar: React.FC<ProviderSidebarProps> = ({
    selectedKey,
    onSelect,
}) => {
    const menuItems = [
        // {
        //     key: "providerUpload",
        //     icon: <UploadIcon />,
        //     label: "Contract Upload",
        // },
        // {
        //     key: "currentItems",
        //     icon: <ListIcon />,
        //     label: "Current Contracts",
        // },

        // {
        //     key: "teamUpload",
        //     icon: <UploadIcon />,
        //     label: "Team Upload",
        // },

        {
            key: "agentUpload",
            icon: <ConstructionIcon />,
            label: "Agent Upload",
        },
        {
            key: "chatbot",
            icon: <MessageCircleIcon />,
            label: "Agent",
        },
    ];

    return (
        <div className="flex flex-col h-full">
            <div className="flex items-center justify-between pb-2 border-b border-secondary w-full px-2 py-2 pb-6">
                <div className="flex items-center gap-2">
                    <span className="text-primary font-medium">
                        Provider Placeholders
                    </span>
                </div>
            </div>
            <Menu
                mode="inline"
                selectedKeys={[selectedKey]}
                style={{ height: "100%", borderRight: 0 }}
                onClick={({ key }) => onSelect(key)}
                items={menuItems}
                className="mt-2"
            />
        </div>
    );
};

export default ProviderSidebar;
