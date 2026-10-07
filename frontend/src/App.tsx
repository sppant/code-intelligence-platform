import { Provider } from "urql";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { client } from "./graphql/client";
import { LandingPage } from "./pages/LandingPage";
import { RepositoryOverviewPage } from "./pages/RepositoryOverviewPage";
import { CodeExplorerPage } from "./pages/CodeExplorerPage";
import { ArchitectureGraphPage } from "./pages/ArchitectureGraphPage";
import "./App.css";

function App() {
  return (
    <Provider value={client}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/repository/:id" element={<RepositoryOverviewPage />} />
          <Route path="/repository/:id/explorer" element={<CodeExplorerPage />} />
          <Route path="/repository/:id/graph" element={<ArchitectureGraphPage />} />
        </Routes>
      </BrowserRouter>
    </Provider>
  );
}

export default App;
