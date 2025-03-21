import React from "react";
import EventLogs from "./eventlog";
import DemoSidebar from "./sidebar";
interface BridgentManagerProps {}
const BridgentManager: React.FC<BridgentManagerProps> = () => {
    return (
        <>
            <div className="grid grid-cols-12 divide-x h-full divide-secondary">
                <div className="col-span-3">
                    <DemoSidebar />
                </div>

                <div className="col-span-9 h-full">
                    <EventLogs />
                </div>
            </div>
        </>
    );
};
export default BridgentManager;
