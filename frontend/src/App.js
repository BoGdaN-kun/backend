import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";
import LiveChart from "./LiveChart";
import StockDetailPage from "./StockDetailsPage";
import SimulationPage from "./SimulatorTrading"
import PortfolioDashboardPage from "./PortfolioDashboardPage";
import WatchlistPage from "./WatchlistPage";
import Layout from "./Layout";
function App() {
    return (
        <BrowserRouter>
            <div className="App">
                <Routes>
                    <Route path="/" element={<Navigate to="/login" replace />} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/register" element={<RegisterPage />} />
                    <Route element={<Layout/>}>

                        <Route path="/chart" element={<LiveChart />} />
                        <Route path="/stock/:symbol" element={<StockDetailPage />} />
                        <Route path="/simulator/" element={<SimulationPage />} />
                        <Route path="/portfolio" element={<PortfolioDashboardPage />} />
                        <Route path="/watchlists" element={<WatchlistPage />} />
                    </Route>
                </Routes>
            </div>
        </BrowserRouter>
    );
}

export default App;