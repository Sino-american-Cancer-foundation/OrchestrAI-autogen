import * as React from "react";
import Layout from "../components/layout";
import { graphql } from "gatsby";
import GalleryManager from "../components/views/gallery/manager";
import { Alert } from "antd";

// Error boundary component
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Gallery error boundary caught error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4">
          <Alert
            message="Error Loading Gallery"
            description={
              <div>
                <p>Something went wrong while loading the gallery:</p>
                <p className="font-mono text-sm">{this.state.error?.toString()}</p>
                <p>Check the browser console for more details.</p>
              </div>
            }
            type="error"
            showIcon
          />
        </div>
      );
    }

    return this.props.children;
  }
}

// markup
const GalleryPage = ({ data }: any) => {
  console.log("Rendering Gallery Page");
  
  return (
    <Layout meta={data.site.siteMetadata} title="Home" link={"/gallery"}>
      <main style={{ height: "100%" }} className="h-full">
        <ErrorBoundary>
          <GalleryManager />
        </ErrorBoundary>
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

export default GalleryPage;
