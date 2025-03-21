import React, { useState } from "react";
import UploadTab from "./uploadTab";
import { Tabs, TabsProps } from "antd";
import VerifyTab from "./verifyTab";

interface UploaderProps {}

const DemoSidebar: React.FC<UploaderProps> = () => {
    const onChange = (key: string) => {
        console.log(key);
    };
    const items: TabsProps["items"] = [
        {
            key: "upload",
            label: "Upload",
            children: <UploadTab />,
        },
        {
            key: "verify",
            label: "Verify",
            children: <VerifyTab />,
        },
    ];
    return (
        <div className="flex flex-col h-full">
            <div className="flex items-center justify-between pb-2 border-b border-secondary w-full px-2 py-2 pb-6">
                <div className="flex items-center gap-2">
                    <span className="text-primary font-medium">
                        Demo Functionality
                    </span>
                </div>
            </div>
            <div>
                <Tabs
                    defaultActiveKey="upload"
                    items={items}
                    onChange={onChange}
                    tabBarStyle={{ padding: "1px 10px" }}
                />
            </div>
        </div>
    );
};

export default DemoSidebar;
