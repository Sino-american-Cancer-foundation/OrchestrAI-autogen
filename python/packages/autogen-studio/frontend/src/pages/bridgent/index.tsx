import * as React from "react";
import Layout from "../../components/layout";
import { graphql } from "gatsby";
import BridgentManager from "../../components/views/bridgent/manager";

// markup
const BridgentPage = ({ data }: any) => {
    return (
        <Layout
            meta={data.site.siteMetadata}
            title="bridgent"
            link={"/bridgent"}
        >
            <main style={{ height: "100%" }} className=" h-full ">
                <BridgentManager />
            </main>
        </Layout>
    );
};

export const query = graphql`
    query HomePageQuery {
        site {
            siteMetadata {
                description
                title
            }
        }
    }
`;

export default BridgentPage;
