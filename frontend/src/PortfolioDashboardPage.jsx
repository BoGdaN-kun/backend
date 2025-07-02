import React, { useState, useEffect, useRef, useCallback } from 'react';

import Chart from 'react-apexcharts';
import {
    Container, Grid, Paper, Typography, Box, CircularProgress, Alert,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip as MuiTooltip, Button
} from '@mui/material';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import PieChartIcon from '@mui/icons-material/PieChart';
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import WalletIcon from "@mui/icons-material/AccountBalanceWallet";
import {useNavigate} from "react-router-dom";
import HistoryIcon from '@mui/icons-material/History';


const API_BASE_URL_TRADING_APP = "http://localhost:5000";
const API_BASE_URL_EXCHANGE_SIM = "http://localhost:9000";
const API_BASE_URL_MARKET_DATA = "http://localhost:8000";


const getAuthToken = () => localStorage.getItem('authToken');

async function fetchWithAuth(url, options = {}) {
    const token = getAuthToken();
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    try {
        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: `Request failed: ${response.status}` }));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        if (response.status === 204 || response.headers.get("content-length") === "0") return null;
        return response.json();
    } catch (error) {
        console.error(`API call error for ${url}:`, error.message);
        throw error;
    }
}


function ApexSparklineChart({ data, height = 40, width = 120 }) {


    const [series, setSeries] = useState([]);
    const [options, setOptions] = useState({});

    useEffect(() => {
        if (data && data.length > 1) {
            const formattedData = data.map(item => ({
                x: item.time * 1000,
                y: item.value
            }));

            setSeries([{ data: formattedData }]);
            setOptions({
                chart: {
                    type: 'line',
                    height: height,
                    width: width,
                    sparkline: {
                        enabled: true
                    },
                    animations: { enabled: false },
                },
                stroke: {
                    curve: 'straight',
                    width: 2,

                    colors: [formattedData[formattedData.length - 1].y >= formattedData[0].y ? '#26a69a' : '#ef5350']
                },
                tooltip: {
                    enabled: false,

                },
                xaxis: { type: 'datetime', labels: { show: false }, axisBorder: { show: false }, axisTicks: { show: false } },
                yaxis: { labels: { show: false } },
                grid: { show: false, padding: { left: 2, right: 2, top: 2, bottom: 2 } },
            });
        } else {
            setSeries([]);
        }
    }, [data, height, width]);

    if (!data || data.length < 2) {
        return <Box sx={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Typography variant="caption" color="text.disabled">N/A</Typography></Box>;
    }


    if (series.length === 0 || Object.keys(options).length === 0) {
        return <Box sx={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><CircularProgress size={20} /></Box>;
    }

    return (
        <Chart
            options={options}
            series={series}
            type="area"
            width={width}
            height={height}
        />
    );
}
function PerformanceBarChart({ holdings, topN = 5 }) {
    const [series, setSeries] = useState([]);
    const [options, setOptions] = useState({});

    useEffect(() => {
        if (holdings && holdings.length > 0) {
            const sortedHoldings = [...holdings].sort((a, b) => a.pnl - b.pnl);


            const losers = sortedHoldings.filter(h => h.pnl < 0).slice(0, topN);
            const gainers = sortedHoldings.filter(h => h.pnl >= 0).reverse().slice(0, topN);


            const chartData = [...losers, ...gainers].reverse();

            const chartSeries = [{
                name: 'Unrealized P&L',
                data: chartData.map(h => ({
                    x: h.symbol,
                    y: h.pnl.toFixed(2),
                })),
            }];

            const chartOptions = {
                chart: {
                    type: 'bar',
                    height: '100%',
                    toolbar: { show: false },
                },
                plotOptions: {
                    bar: {
                        horizontal: false,
                        barHeight: '60%',
                        colors: {
                            ranges: [{
                                from: -Infinity,
                                to: -0.01,
                                color: '#ef5350'
                            }, {
                                from: 0,
                                to: Infinity,
                                color: '#26a69a'
                            }]
                        },
                    },
                },
                dataLabels: {
                    enabled: true,
                    formatter: function (val) {
                        return `$${val}`;
                    },
                    offsetX: 25,
                    style: {
                        fontSize: '12px',
                        colors: ['#333']
                    }
                },
                xaxis: {
                    categories: chartData.map(h => h.symbol),
                    labels: {
                        formatter: function(val) {
                            return `$${val}`;
                        }
                    },
                    title: { text: 'Unrealized P&L ($)' }
                },
                yaxis: {
                    labels: {
                        show: true,
                    }
                },
                tooltip: {
                    y: {
                        formatter: (val) => `$${val}`
                    }
                },
                grid: {
                    xaxis: { lines: { show: true } }
                },
                noData: { text: 'No P&L data to display.' }
            };

            setSeries(chartSeries);
            setOptions(chartOptions);
        }
    }, [holdings, topN]);

    if (!holdings || holdings.length === 0) {
        return <Typography color="text.secondary" sx={{textAlign:'center', mt:5}}>No holdings to analyze performance.</Typography>
    }

    return (
        <Chart
            options={options}
            series={series}
            type="bar"
            width="100%"
            height="100%"
        />
    );
}


function TransactionHistory() {
    const [trades, setTrades] = useState([]);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchTrades = useCallback(async (pageNum) => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchWithAuth(`${API_BASE_URL_EXCHANGE_SIM}/trades?page=${pageNum}&per_page=10`);
            setTrades(prev => pageNum === 1 ? data.trades : [...prev, ...data.trades]);
            setHasMore(data.has_next);
        } catch (err) {
            setError(err.message || 'Failed to load transactions.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {

        fetchTrades(1);
    }, [fetchTrades]);

    const handleShowMore = () => {
        const nextPage = page + 1;
        setPage(nextPage);
        fetchTrades(nextPage);
    };

    return (
        <Paper elevation={3} sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 'medium', mb: 2 }}>
                <HistoryIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                Transaction History
            </Typography>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <TableRow sx={{ '& th': { fontWeight: 'bold', color: 'text.secondary' } }}>
                            <TableCell>Date</TableCell>
                            <TableCell>Symbol</TableCell>
                            <TableCell>Side</TableCell>
                            <TableCell align="right">Quantity</TableCell>
                            <TableCell align="right">Price</TableCell>
                            <TableCell align="right">Total Value</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {trades.map(trade => (
                            <TableRow key={trade.id}>
                                <TableCell>{new Date(trade.timestamp).toLocaleString()}</TableCell>
                                <TableCell sx={{ fontWeight: 'bold' }}>{trade.symbol}</TableCell>
                                <TableCell>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: trade.side === 'buy' ? 'success.dark' : 'error.dark',
                                            textTransform: 'capitalize'
                                        }}
                                    >
                                        {trade.side}
                                    </Typography>
                                </TableCell>
                                <TableCell align="right">{trade.quantity}</TableCell>
                                <TableCell align="right">${trade.price.toFixed(2)}</TableCell>
                                <TableCell align="right">${(trade.quantity * trade.price).toFixed(2)}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
            {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
            {trades.length === 0 && !loading && !error &&
                <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>No transactions found.</Typography>
            }
            <Box sx={{ textAlign: 'center', mt: 2 }}>
                {hasMore && (
                    <Button onClick={handleShowMore} disabled={loading}>
                        {loading ? <CircularProgress size={24} /> : 'Show More'}
                    </Button>
                )}
            </Box>
        </Paper>
    );
}



export default function PortfolioDashboardPage() {
    const [portfolioState, setPortfolioState] = useState({
        holdings: [],
        cashBalance: 0,
        totalPortfolioValue: 0,
        totalPortfolioPnL: 0,
        allocationDataForChart: { series: [], options: {} },
    });
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const positionsResponse = await fetchWithAuth(`${API_BASE_URL_EXCHANGE_SIM}/portfolio`);
            const cashResponse = await fetchWithAuth(`${API_BASE_URL_TRADING_APP}/account/balance`);
            const currentCashBalance = cashResponse.balance || 0;

            const symbols = positionsResponse.map(p => p.symbol);
            let marketPrices = {};
            let sparklineDataFetches = [];

            if (symbols.length > 0) {
                const pricePromises = symbols.map(symbol =>
                    fetch(`${API_BASE_URL_MARKET_DATA}/candles?symbol=${symbol}&limit=1`)
                        .then(res => res.ok ? res.json() : Promise.resolve([{close: 0}]))
                        .then(data => ({ symbol, price: data.length > 0 ? parseFloat(data[0].close) : 0 }))
                        .catch(e => { console.warn(`Price fetch error ${symbol}:`, e.message); return { symbol, price: 0 }; })
                );
                const pricesData = await Promise.all(pricePromises);
                pricesData.forEach(pd => { marketPrices[pd.symbol] = pd.price; });

                sparklineDataFetches = symbols.map(symbol =>
                    fetch(`${API_BASE_URL_MARKET_DATA}/sparkline/${symbol}?days=7`)
                        .then(res => res.ok ? res.json() : Promise.resolve([]))
                        .then(data => ({
                            symbol,
                            sparkline: data.map(d => ({ time: d.time, value: d.close }))
                        }))
                        .catch(e => { console.warn(`Sparkline fetch error ${symbol}:`, e.message); return { symbol, sparkline: [] }; })
                );
            }

            const sparklineResults = await Promise.all(sparklineDataFetches);
            const sparklinesMap = {};
            sparklineResults.forEach(sr => { sparklinesMap[sr.symbol] = sr.sparkline; });

            let newTotalPortfolioValue = currentCashBalance;
            let newTotalPortfolioPnL = 0;

            const newHoldings = positionsResponse.map(pos => {
                const currentPrice = marketPrices[pos.symbol] || 0;
                const currentValue = pos.quantity * currentPrice;
                let averageCost = 0;
                if (pos.average_cost_price !== undefined) averageCost = parseFloat(pos.average_cost_price);
                else if (pos.average_cost_price_cents !== undefined && pos.quantity > 0) averageCost = parseFloat(pos.average_cost_price_cents) / 100;
                else if (pos.total_cost_cents !== undefined && pos.quantity > 0) averageCost = (parseFloat(pos.total_cost_cents) / pos.quantity) / 100;

                const costBasisValue = pos.quantity * averageCost;
                const pnl = (averageCost > 0 && pos.quantity > 0) ? currentValue - costBasisValue : 0;
                const pnlPercent = costBasisValue !== 0 ? (pnl / costBasisValue) * 100 : 0;

                newTotalPortfolioValue += currentValue;
                newTotalPortfolioPnL += pnl;

                return {
                    symbol: pos.symbol, quantity: pos.quantity, averageCost,
                    currentPrice, currentValue, pnl, pnlPercent,
                    sparklineData: sparklinesMap[pos.symbol] || []
                };
            });


            const allocationSeries = newHoldings.filter(h => h.currentValue > 0).map(h => parseFloat(h.currentValue.toFixed(2)));
            const allocationLabels = newHoldings.filter(h => h.currentValue > 0).map(h => h.symbol);

            const allocationChartOptions = {
                chart: { type: 'pie', height: '100%', foreColor: '#373d3f' },
                labels: allocationLabels,
                theme: { mode: 'light' },
                responsive: [{
                    breakpoint: 480,
                    options: { chart: { width: 200 }, legend: { position: 'bottom' } }
                }],
                legend: { position: 'bottom', labels: { colors: ['#373d3f'] } },
                tooltip: {
                    y: { formatter: (val) => `$${val.toFixed(2)}` }
                }
            };

            setPortfolioState({
                holdings: newHoldings, cashBalance: currentCashBalance,
                totalPortfolioValue: newTotalPortfolioValue, totalPortfolioPnL: newTotalPortfolioPnL,
                allocationDataForChart: { series: allocationSeries, options: allocationChartOptions },
            });

        } catch (err) {
            setError(err.message || "Could not load dashboard data.");
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const intervalId = setInterval(fetchData, 60000);
        return () => clearInterval(intervalId);
    }, [fetchData]);
    const navigate = useNavigate();
    if (isLoading) return <Container sx={{mt:4, textAlign:'center'}}><CircularProgress size={60} /></Container>;
    if (error) return <Container sx={{mt:4}}><Alert severity="error">Error loading portfolio: {error}</Alert></Container>;

    return (
        <Container maxWidth="xl" sx={{ mt: 2, mb: 4 }}>
            <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3, color: "primary.main" }}>
                Portfolio Dashboard
            </Typography>

            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} sm={6} md={4}>
                    <Paper elevation={3} sx={{ p: 2, textAlign: 'center', borderRadius: 2 }}>
                        <WalletIcon color="primary" sx={{ fontSize: 36, mb: 1 }}/>
                        <Typography variant="overline" color="text.secondary">Total Portfolio Value</Typography>
                        <Typography variant="h5" sx={{ fontWeight: 'medium' }}>
                            ${portfolioState.totalPortfolioValue.toFixed(2)}
                        </Typography>
                    </Paper>
                </Grid>
                <Grid item xs={12} sm={6} md={4}>
                    <Paper elevation={3} sx={{ p: 2, textAlign: 'center', borderRadius: 2 }}>
                        <ShowChartIcon sx={{ fontSize: 36, mb: 1, color: portfolioState.totalPortfolioPnL >= 0 ? 'success.main' : 'error.main' }}/>
                        <Typography variant="overline" color="text.secondary">Total Unrealized P&L</Typography>
                        <Typography variant="h5" sx={{ fontWeight: 'medium', color: portfolioState.totalPortfolioPnL >= 0 ? 'success.main' : 'error.main' }}>
                            ${portfolioState.totalPortfolioPnL.toFixed(2)}
                        </Typography>
                    </Paper>
                </Grid>
                <Grid item xs={12} sm={12} md={4}>
                    <Paper elevation={3} sx={{ p: 2, textAlign: 'center', borderRadius: 2 }}>
                        <AttachMoneyIcon color="action" sx={{ fontSize: 36, mb: 1 }}/>
                        <Typography variant="overline" color="text.secondary">Cash Balance</Typography>
                        <Typography variant="h5" sx={{ fontWeight: 'medium' }}>
                            ${portfolioState.cashBalance.toFixed(2)}
                        </Typography>
                    </Paper>
                </Grid>
            </Grid>
            <Grid container spacing={3}>
                <Grid item xs={12} lg={7}>
                    <Paper elevation={3} sx={{ p: 2, borderRadius: 2 }}>
                        <Typography variant="h6" gutterBottom sx={{ fontWeight: 'medium', mb:2 }}>My Holdings</Typography>
                        <TableContainer>
                            <Table size="small" aria-label="portfolio holdings table">
                                <TableHead>
                                    <TableRow sx={{ '& th': { fontWeight: 'bold', color: 'text.secondary', whiteSpace: 'nowrap', py:1 } }}>
                                        <TableCell>Symbol</TableCell>
                                        <TableCell sx={{minWidth: 130, textAlign:'center'}}>Trend (7D)</TableCell>
                                        <TableCell align="right">Quantity</TableCell>
                                        <TableCell align="right">Avg. Cost</TableCell>
                                        <TableCell align="right">Current Price</TableCell>
                                        <TableCell align="right">Market Value</TableCell>
                                        <TableCell align="right">Unrealized P&L</TableCell>
                                        <TableCell align="right">P&L %</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {portfolioState.holdings.length > 0 ? portfolioState.holdings.map((h) => (
                                        <TableRow key={h.symbol} hover sx={{ '& td': { whiteSpace: 'nowrap', py: 0.5} }}>
                                            <TableCell component="th" scope="row" sx={{ fontWeight: 'medium', cursor: 'pointer','&:hover': {
                                                    textDecoration: 'underline',
                                                    color: 'primary.main',
                                                } }} onClick={() => navigate(`../stock/${h.symbol}`)}>{h.symbol}</TableCell>
                                            <TableCell sx={{p:0}}>
                                                <Box sx={{height: 40, width: 120, mx: 'auto'}}>
                                                    <ApexSparklineChart data={h.sparklineData} width={120} height={40}/>
                                                </Box>
                                            </TableCell>
                                            <TableCell align="right">{h.quantity}</TableCell>
                                            <TableCell align="right">${h.averageCost ? h.averageCost.toFixed(2) : 'N/A'}</TableCell>
                                            <TableCell align="right">${h.currentPrice ? h.currentPrice.toFixed(2) : 'N/A'}</TableCell>
                                            <TableCell align="right">${h.currentValue.toFixed(2)}</TableCell>
                                            <TableCell align="right" sx={{ color: h.pnl >= 0 ? 'success.dark' : 'error.dark' }}>
                                                {h.pnl ? h.pnl.toFixed(2) : 'N/A'}
                                            </TableCell>
                                            <TableCell align="right" sx={{ color: h.pnlPercent >= 0 ? 'success.dark' : 'error.dark' }}>
                                                {typeof h.pnlPercent === 'number' ? h.pnlPercent.toFixed(2) : 'N/A'}%
                                            </TableCell>
                                        </TableRow>
                                    )) : (
                                        <TableRow>
                                            <TableCell colSpan={8} align="center">
                                                <Typography color="text.secondary" sx={{py:3}}>You have no holdings.</Typography>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                </Grid>
                <Grid item xs={12} lg={5}>
                    <Paper elevation={3} sx={{ p: 2, height: 'auto', minHeight: {xs: 280, md: 350}, display: 'flex', flexDirection:'column', alignItems:'center', borderRadius: 2 }}>
                        <Typography variant="h6" gutterBottom sx={{ fontWeight: 'medium', mb:2, alignSelf:'flex-start' }}>
                            Asset Allocation
                            <MuiTooltip title="Allocation by current market value of holdings.">
                                <InfoOutlinedIcon fontSize="small" color="action" sx={{ml:0.5, verticalAlign:'middle'}}/>
                            </MuiTooltip>
                        </Typography>
                        {portfolioState.allocationDataForChart.series.length > 0 ? (
                            <Box sx={{width: '100%', height: {xs: 200, sm: 250, md: 300} }}>
                                <Chart
                                    options={portfolioState.allocationDataForChart.options}
                                    series={portfolioState.allocationDataForChart.series}
                                    type="pie"
                                    width="100%"
                                    height="100%"
                                />
                            </Box>
                        ) : (
                            <Typography color="text.secondary" sx={{textAlign:'center', mt:'20%'}}>No data for allocation chart.</Typography>
                        )}
                    </Paper>
                </Grid>
            </Grid>
            <Grid container spacing={3}  sx={{ mt: 3 }}>
                <Grid item xs={12} md={10} lg={8}>
                    <Paper elevation={3} sx={{ p: 2, height: 400, borderRadius: 2 }}>
                        <Typography variant="h6" gutterBottom sx={{ fontWeight: 'medium', mb: 2 }}>
                            Top & Bottom Performers (by Unrealized P&L)
                        </Typography>
                        <Box sx={{ width: '100%', height: 'calc(100% - 48px)' }}>
                            <PerformanceBarChart holdings={portfolioState.holdings} />
                        </Box>
                    </Paper>
                </Grid>

                <Grid item xs={12}>
                    <TransactionHistory />
                </Grid>

            </Grid>
        </Container>
    );
}