import React, {useState, useEffect, useRef, useCallback} from 'react';
import {Card, CardContent, CardMedia, CircularProgress} from '@mui/material';
import LaunchIcon from '@mui/icons-material/Launch';
import * as LightweightCharts from 'lightweight-charts';
import {
    AppBar, Toolbar, Typography, Box, Button, Container, Grid, Paper,
    TextField, Select, MenuItem, Snackbar, Alert, ButtonGroup, FormControl, InputLabel
} from '@mui/material';
import WalletIcon from '@mui/icons-material/AccountBalanceWallet';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import HistoryIcon from '@mui/icons-material/History';
import BusinessCenterIcon from '@mui/icons-material/BusinessCenter';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import {useParams} from "react-router-dom";

const API_BASE_URL_TRADING_APP = "http://localhost:5000";
const API_BASE_URL_EXCHANGE_SIM = "http://localhost:9000";
const API_BASE_URL_MARKET_DATA = "http://localhost:8000";

const getAuthToken = () => localStorage.getItem('authToken');

async function fetchWithAuth(url, options = {}) {
    const token = getAuthToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(url, {...options, headers});
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({error: 'Request failed'}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
    }
    return response.json();
}

function TopBar({stockSymbol}) {
    const [balance, setBalance] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchBalance = async () => {
            try {
                const data = await fetchWithAuth(`${API_BASE_URL_TRADING_APP}/account/balance`);
                setBalance(data.balance);
            } catch (err) {
                setError(err.message);
            }
        };
        fetchBalance();
        const intervalId = setInterval(fetchBalance, 30000);
        return () => clearInterval(intervalId);
    }, []);

    return (
        <AppBar position="static" color="primary">
            <Toolbar sx={{display: 'flex', justifyContent: 'space-between'}}>
                <Typography variant="h6">Stock Detail: {stockSymbol}</Typography>
                <Box display="flex" alignItems="center">
                    {error && <Typography color="error" sx={{mr: 2}}>Balance Error</Typography>}
                    {balance !== null ? (
                        <Typography>
                            <WalletIcon sx={{verticalAlign: 'middle', mr: 1}}/>
                            Balance: ${balance.toFixed(2)}
                        </Typography>
                    ) : (
                        <Typography>Loading balance...</Typography>
                    )}
                </Box>
            </Toolbar>
        </AppBar>
    );
}

function LiveChartLW({bootstrapEndpoint, pollEndpoint, pollMs = 2000, height = 400, chartKey}) {
    const containerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const pollingTimerRef = useRef(null);

    const toLWFormat = useCallback(c => ({
        time: parseInt(c.time, 10),
        open: parseFloat(c.open),
        high: parseFloat(c.high),
        low: parseFloat(c.low),
        close: parseFloat(c.close),
    }), []);

    useEffect(() => {
        if (!containerRef.current) return;

        const chart = LightweightCharts.createChart(containerRef.current, {
            height,
            layout: {textColor: '#D1D4DC', background: {type: LightweightCharts.ColorType.Solid, color: '#1E222D'}},
            grid: {horzLines: {color: '#2B2E38'}, vertLines: {color: '#2B2E38'}},
            timeScale: {timeVisible: true, secondsVisible: false},
        });
        chartRef.current = chart;

        if (LightweightCharts.CandlestickSeries) {
            const candleSeries = chart.addSeries(
                LightweightCharts.CandlestickSeries,
                {
                    upColor: '#26a69a', downColor: '#ef5350',
                    wickUpColor: '#26a69a', wickDownColor: '#ef5350',
                    borderVisible: false,
                }
            );
            seriesRef.current = candleSeries;
        } else {
            console.error("LightweightCharts.CandlestickSeries constructor is not available.");
            return;
        }

        let isMounted = true;

        const bootstrapData = async () => {
            try {
                const response = await fetch(bootstrapEndpoint);
                const data = (await response.json()).map(toLWFormat);
                console.log("Formatted candles for chart:", data);
                if (isMounted) {
                    seriesRef.current.setData(data);
                }

            } catch (err) {
                console.error('Bootstrap error:', err);
            }
        };

        const pollData = async () => {
            try {
                const response = await fetch(pollEndpoint);
                const liveCandles = (await response.json()).map(toLWFormat);
                if (isMounted && liveCandles.length > 0) {
                    liveCandles.forEach(candle => seriesRef.current.update(candle));
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        };

        bootstrapData().then(() => {
            if (pollEndpoint) {
                pollData();
                pollingTimerRef.current = setInterval(pollData, pollMs);
            }
        });

        return () => {
            isMounted = false;
            clearInterval(pollingTimerRef.current);
            chart.remove();
        };
    }, [bootstrapEndpoint, pollEndpoint, pollMs, height, toLWFormat, chartKey]);

    return <div ref={containerRef} style={{width: '100%', height: `${height}px`}}/>;
}

function getLastTradingDay(date) {
    const result = new Date(date);


    if (result.getDay() === 0) {
        result.setDate(result.getDate() - 2);
    } else if (result.getDay() === 6) {
        result.setDate(result.getDate() - 1);
    }

    return result;
}

function subtractTradingDays(date, numDays) {
    const result = new Date(date);
    let daysSubtracted = 0;

    while (daysSubtracted < numDays) {
        result.setDate(result.getDate() - 1);


        const day = result.getDay();
        if (day !== 0 && day !== 6) {
            daysSubtracted++;
        }
    }

    return result;
}

function ChartContainer({stockSymbol}) {
    const [timeRange, setTimeRange] = useState('LIVE');
    const [chartKey, setChartKey] = useState(Date.now());
    const [chartConfig, setChartConfig] = useState({
        bootstrapEndpoint: `${API_BASE_URL_MARKET_DATA}/today/${stockSymbol}`,
        pollEndpoint: `${API_BASE_URL_MARKET_DATA}/candles?symbol=${stockSymbol}&limit=5`,
        pollMs: 2000
    });
    console.log(`${API_BASE_URL_MARKET_DATA}/today/${stockSymbol}`);
    const handleTimeRangeChange = (range) => {
        setTimeRange(range);
        setChartKey(Date.now());

        if (range === 'LIVE') {
            setChartConfig({
                bootstrapEndpoint: `${API_BASE_URL_MARKET_DATA}/today/${stockSymbol}`,
                pollEndpoint: `${API_BASE_URL_MARKET_DATA}/candles?symbol=${stockSymbol}&limit=5`,
                pollMs: 2000
            });
        } else {
            const today = new Date();
            const endDate = getLastTradingDay(today);
            let startDate = new Date(endDate);

            let granularity = '1d';

            switch (range) {
                case '1D':
                    startDate = subtractTradingDays(endDate, 0);
                    console.log(startDate);
                    console.log(endDate);
                    granularity = '1m';
                    break;
                case '3D':
                    startDate = subtractTradingDays(endDate, 2);
                    granularity = '1m';
                    break;
                case '5D':
                    startDate = subtractTradingDays(endDate, 4);
                    granularity = '1h';
                    break;
                case '1M':
                    startDate.setMonth(endDate.getMonth() - 1);
                    granularity = '1d';
                    break;
                case '3M':
                    startDate.setMonth(endDate.getMonth() - 3);
                    granularity = '1d';
                    break;
                case '1Y':
                    startDate.setFullYear(endDate.getFullYear() - 1);
                    granularity = '1d';
                    break;
                default:
                    startDate = new Date(endDate);
            }

            const formatDate = (d) => d.toISOString().split('T')[0];

            const startDateStr = formatDate(startDate);
            const endDateStr = formatDate(endDate);

            setChartConfig({
                bootstrapEndpoint: `${API_BASE_URL_MARKET_DATA}/history/${stockSymbol}/${startDateStr}/${endDateStr}/${granularity}`,
                pollEndpoint: null,
                pollMs: 0
            });
        }
    };

    return (
        <Box>
            <ButtonGroup variant="outlined" fullWidth sx={{mb: 2}}>
                {['LIVE', '1D', '3D', '5D', '1M', '3M', '1Y'].map(range => (
                    <Button
                        key={range}
                        onClick={() => handleTimeRangeChange(range)}
                        variant={timeRange === range ? 'contained' : 'outlined'}
                    >
                        {range}
                    </Button>
                ))}
            </ButtonGroup>

            <LiveChartLW
                key={chartKey}
                bootstrapEndpoint={chartConfig.bootstrapEndpoint}
                pollEndpoint={chartConfig.pollEndpoint}
                pollMs={chartConfig.pollMs}
                height={500}
            />
        </Box>
    );
}


function TradingPanel({stockSymbol}) {
    const [orderType, setOrderType] = useState('LIMIT');
    const [side, setSide] = useState('BUY');
    const [quantity, setQuantity] = useState('');
    const [limitPrice, setLimitPrice] = useState('');
    const [snackbar, setSnackbar] = useState({open: false, message: '', severity: 'info'});
    const [loading, setLoading] = useState(false);

    const handlePlaceOrder = async (e) => {
        e.preventDefault();
        setLoading(true);

        const orderData = {
            symbol: stockSymbol,
            side: side.toLowerCase(),
            type: orderType.toLowerCase(),
            quantity: parseInt(quantity, 10),
            limit_price: orderType === 'LIMIT' ? parseFloat(limitPrice) : null,
        };

        if (!orderData.quantity || orderData.quantity <= 0) {
            setSnackbar({open: true, message: 'Please enter a valid quantity.', severity: 'error'});
            setLoading(false);
            return;
        }

        if (orderData.type === 'limit' && (!orderData.limit_price || orderData.limit_price <= 0)) {
            setSnackbar({open: true, message: 'Please enter a valid limit price.', severity: 'error'});
            setLoading(false);
            return;
        }

        try {
            const result = await fetchWithAuth(`${API_BASE_URL_EXCHANGE_SIM}/orders`, {
                method: 'POST',
                body: JSON.stringify(orderData),
            });

            if (result.matching_error) {
                setSnackbar({
                    open: true,
                    message: `Order placed, but with a warning: ${result.matching_error}`,
                    severity: 'warning'
                });
            } else {
                setSnackbar({
                    open: true,
                    message: `Order placed successfully! Order ID: ${result.id}`,
                    severity: 'success'
                });
            }

            setQuantity('');
            setLimitPrice('');

        } catch (error) {
            setSnackbar({open: true, message: `Error placing order: ${error.message}`, severity: 'error'});
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box component="form" onSubmit={handlePlaceOrder}>
            <Typography variant="h6" gutterBottom>Trade {stockSymbol}</Typography>

            <FormControl fullWidth margin="normal">
                <InputLabel>Order Type</InputLabel>
                <Select value={orderType} label="Order Type" onChange={(e) => setOrderType(e.target.value)}>
                    <MenuItem value="LIMIT">Limit</MenuItem>
                    <MenuItem value="MARKET">Market</MenuItem>
                </Select>
            </FormControl>

            {orderType === 'LIMIT' && (
                <TextField
                    fullWidth
                    label="Limit Price"
                    type="number"
                    value={limitPrice}
                    onChange={(e) => setLimitPrice(e.target.value)}
                    margin="normal"
                    required
                    inputProps={{step: "0.01"}}
                />
            )}

            <TextField
                fullWidth
                label="Quantity"
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                margin="normal"
                required
                inputProps={{min: "1"}}
            />

            <Box display="flex" justifyContent="space-between" my={2}>
                <Button variant={side === 'BUY' ? 'contained' : 'outlined'} color="success"
                        onClick={() => setSide('BUY')}>
                    <TrendingUpIcon sx={{mr: 1}}/>Buy
                </Button>
                <Button variant={side === 'SELL' ? 'contained' : 'outlined'} color="error"
                        onClick={() => setSide('SELL')}>
                    <TrendingDownIcon sx={{mr: 1}}/>Sell
                </Button>
            </Box>

            <Button fullWidth variant="contained" type="submit" disabled={loading}>
                {loading ? <CircularProgress size={24}/> : `Submit ${side} Order`}
            </Button>

            <Snackbar open={snackbar.open} autoHideDuration={6000}
                      onClose={() => setSnackbar({...snackbar, open: false})}>
                <Alert onClose={() => setSnackbar({...snackbar, open: false})} severity={snackbar.severity}
                       sx={{width: '100%'}}>
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
}


function NewsPanel({stockSymbol}) {
    const [newsItems, setNewsItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchNews = async () => {
            if (!stockSymbol) return;
            setLoading(true);
            setError(null);
            try {
                const data = await fetchWithAuth(`${API_BASE_URL_MARKET_DATA}/news/${stockSymbol}`);
                setNewsItems(Array.isArray(data) ? data : []);
            } catch (err) {
                console.error("Error fetching news:", err);
                setError(err.message || "Failed to load news.");
                setNewsItems([]);
            } finally {
                setLoading(false);
            }
        };

        fetchNews();

    }, [stockSymbol]);

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center"
                 sx={{p: 2, minHeight: 150 /* Adjusted minHeight */}}>
                <CircularProgress/>
                <Typography sx={{ml: 2}}>Loading news...</Typography>
            </Box>
        );
    }

    if (error) {
        return (
            <Box sx={{p: 2}}>
                <Alert severity="error">Error loading news: {error}</Alert>
            </Box>
        );
    }

    if (newsItems.length === 0) {
        return (
            <Box sx={{p: 2}}>
                <Typography>No news available for {stockSymbol}.</Typography>
            </Box>
        );
    }

    return (
        <Box sx={{p: 1}}>
            <Typography variant="h6" gutterBottom align="center">News: {stockSymbol}</Typography>
            <Box sx={{maxHeight: {xs: '300px', md: '400px'}, overflowY: 'auto', pr: 1 }}>
                {newsItems.map((item, index) => (
                    <Card key={item.uuid || index}
                          sx={{mb: 2, boxShadow: 2, borderRadius: '8px'}}> {/* uuid if available, else index */}
                        {item.thumbnailURL && (
                            <CardMedia
                                component="img"
                                height="100"
                                image={item.thumbnailURL}
                                alt={item.title || "News thumbnail"}

                                onError={(e) => {
                                    e.target.style.display = 'none';
                                }}
                            />
                        )}
                        <CardContent>
                            <Typography gutterBottom variant="subtitle1" component="div" sx={{fontWeight: 'bold'}}>
                                {item.title}
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{mb: 1}}>
                                {item.summary}
                            </Typography>
                            <Typography variant="caption" display="block" color="text.secondary">
                                {/* pub date to be valid */}
                                {item.pubDate ? new Date(item.pubDate).toLocaleString() : 'Date not available'}
                            </Typography>
                        </CardContent>
                        <Box sx={{p: 1, display: 'flex', justifyContent: 'flex-end'}}>
                            {item.newsPage && (
                                <Button
                                    size="small"
                                    href={item.newsPage}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    endIcon={<LaunchIcon/>}
                                >
                                    Read More
                                </Button>
                            )}
                        </Box>
                    </Card>
                ))}
            </Box>
        </Box>
    );
}


export default function StockDetailPage() {
    const {symbol} = useParams();
    const stockSymbol = symbol.toUpperCase();
    return (


        <Box sx={{minHeight: '100vh', bgcolor: 'grey.100'}}> {/* Height  */}
            <TopBar stockSymbol={stockSymbol}/>
            <Container maxWidth="xl" sx={{py: 2, height: 'calc(100vh - 64px)'}}>
                <Box
                    sx={{
                        display: 'grid',
                        gridTemplateColumns: '2fr 1fr',
                        gap: 2,
                        height: '100%',
                    }}
                >
                    {/* Chart */}
                    <Paper
                        elevation={3}
                        sx={{
                            p: 2,
                            height: '77%',
                            borderRadius: 3,
                            display: 'flex',
                            flexDirection: 'column',
                        }}
                    >
                        <ChartContainer stockSymbol={stockSymbol}/>
                    </Paper>

                    {/* Right Panel: Trading + News stacked */}
                    <Box
                        sx={{
                            display: 'grid',
                            gridTemplateRows: 'auto 1fr',
                            gap: 2,
                            height: '80%',
                        }}
                    >
                        {/* Trading Panel */}
                        <Paper
                            elevation={3}
                            sx={{
                                p: 2,
                                borderRadius: 3,
                            }}
                        >
                            <TradingPanel stockSymbol={stockSymbol}/>
                        </Paper>

                        {/* News Panel */}
                        <Paper
                            elevation={3}
                            sx={{
                                p: 2,
                                borderRadius: 3,
                                overflowY: 'auto',
                                minHeight: 0,
                            }}
                        >
                            <NewsPanel stockSymbol={stockSymbol}/>
                        </Paper>
                    </Box>
                </Box>
            </Container>

        </Box>
    );
}

