import * as React from "react";
import Layout from "../../components/layout";
import { graphql } from "gatsby";
import PlaceholderManager from "../../components/views/placeholder/manager";

// markup
const PlaceholderPage = ({ data }: any) => {
    return (
        <Layout
            meta={data.site.siteMetadata}
            title="placeholder"
            link={"/placeholder"}
        >
            <main style={{ height: "100%" }} className=" h-full ">
                <PlaceholderManager />
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

export default PlaceholderPage;
