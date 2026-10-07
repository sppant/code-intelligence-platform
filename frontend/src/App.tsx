import { Provider } from "urql";
import { client } from "./graphql/client";
import { LandingPage } from "./pages/LandingPage";
import "./App.css";

function App() {
  return (
    <Provider value={client}>
      <LandingPage />
    </Provider>
  );
}

export default App;
