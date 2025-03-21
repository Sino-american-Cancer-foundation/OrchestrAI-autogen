import { List } from "antd";
import { ChevronRight } from "lucide-react";
import React from "react";
interface ItemsPageProps {}
const ItemsPage: React.FC<ItemsPageProps> = () => {
    const data = Array.from({ length: 23 }).map((_, i) => ({
        title: `Contract ${i}`,
        description: "A sample contract",
        content: "Contract description.",
    }));
    return (
        <>
            <div className="flex items-center gap-2 text-sm p-2 px-4">
                <span className="text-primary font-medium">
                    Provider Placeholders
                </span>
                <ChevronRight className="w-4 h-4 text-secondary" />
                <span className="text-secondary">Current Contracts</span>
            </div>
            <div className="flex flex-grow flex-col w-full pl-4">
                <div className="text-3xl font-bold py-4">Current Contracts</div>
                <List
                    className="flex-grow overflow-y-auto"
                    itemLayout="vertical"
                    pagination={{
                        onChange: (page) => {
                            console.log(page);
                        },
                        pageSize: 5,
                    }}
                    dataSource={data}
                    footer={
                        <div>
                            <b>ant design</b> footer part
                        </div>
                    }
                    renderItem={(item) => (
                        <List.Item key={item.title}>
                            <List.Item.Meta
                                title={item.title}
                                description={item.description}
                            />
                            {item.content}
                        </List.Item>
                    )}
                />
            </div>
        </>
    );
};
export default ItemsPage;
