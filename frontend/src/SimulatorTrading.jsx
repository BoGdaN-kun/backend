import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as LightweightCharts from 'lightweight-charts';
import {
    AppBar, Toolbar, Typography, Box, Button, Container, Grid, Paper,
    TextField, Select, MenuItem, Alert, ButtonGroup, FormControl, InputLabel,
    CircularProgress
} from '@mui/material';

import WalletIcon from '@mui/icons-material/AccountBalanceWallet';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import ReplayIcon from '@mui/icons-material/Replay';


const API_BASE_URL_MARKET_DATA = "http://localhost:8000";

const formatDateForAPI = (date) => {
    return date.toISOString().split('T')[0];
};

function SimulationLiveChart({ data, chartKey }) {
    const containerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const resizeObserverRef = useRef(null);
    const isDisposedRef = useRef(false);
    const resizeTimeoutRef = useRef(null);

    const toLWFormat = useCallback(c => ({
        time: Number(c.time),
        open: parseFloat(c.open),
        high: parseFloat(c.high),
        low: parseFloat(c.low),
        close: parseFloat(c.close),
    }), []);


    const debouncedResize = useCallback(() => {
        if (resizeTimeoutRef.current) {
            clearTimeout(resizeTimeoutRef.current);
        }

        resizeTimeoutRef.current = setTimeout(() => {
            if (chartRef.current && containerRef.current && !isDisposedRef.current) {
                try {
                    const { clientWidth, clientHeight } = containerRef.current;
                    if (clientWidth > 0 && clientHeight > 0) {
                        chartRef.current.resize(clientWidth, clientHeight);
                    }
                } catch (error) {
                    console.warn("Error resizing chart:", error);
                }
            }
        }, 100);
    }, []);


    useEffect(() => {
        if (!containerRef.current?.isConnected) return;

        isDisposedRef.current = false;

        const initChart = () => {
            const container = containerRef.current;
            if (!container || container.clientWidth === 0 || container.clientHeight === 0) {
                setTimeout(initChart, 50);
                return;
            }

            const chartOptions = {
                height: container.clientHeight,
                width: container.clientWidth,
                layout: {
                    textColor: '#D1D4DC',
                    background: { type: LightweightCharts.ColorType.Solid, color: '#171A25' }
                },
                grid: {
                    horzLines: { color: '#2A2E39' },
                    vertLines: { color: '#2A2E39' }
                },
                timeScale: {
                    timeVisible: true,
                    secondsVisible: false,
                    borderColor: '#484C58',
                    fixLeftEdge: true,
                    fixRightEdge: true
                },
                rightPriceScale: { borderColor: '#484C58' },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                handleScroll: true,
                handleScale: true,
            };

            try {
                const chart = LightweightCharts.createChart(container, chartOptions);
                chartRef.current = chart;

                if (LightweightCharts.CandlestickSeries) {
                    const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
                        upColor: '#00b894',
                        downColor: '#f44336',
                        wickUpColor: '#00b894',
                        wickDownColor: '#f44336',
                        borderVisible: false,
                    });
                    seriesRef.current = candleSeries;

                    if (data?.length > 0) {
                        const formattedData = data.map(toLWFormat);
                        candleSeries.setData(formattedData);
                        requestAnimationFrame(() => {
                            if (chart && !isDisposedRef.current) {
                                chart.timeScale().fitContent();
                            }
                        });
                    }
                }
            } catch (error) {
                console.error("Error creating chart:", error);
            }
        };

        initChart();

        return () => {
            isDisposedRef.current = true;
            if (resizeTimeoutRef.current) {
                clearTimeout(resizeTimeoutRef.current);
            }
            if (chartRef.current) {
                try {
                    chartRef.current.remove();
                } catch (error) {
                    console.warn("Error disposing chart:", error);
                }
                chartRef.current = null;
                seriesRef.current = null;
            }
        };
    }, [data, toLWFormat, chartKey]);


    useEffect(() => {
        const container = containerRef.current;
        if (!container || !chartRef.current) return;


        if (ResizeObserver) {
            const resizeObserver = new ResizeObserver(debouncedResize);
            resizeObserverRef.current = resizeObserver;
            resizeObserver.observe(container);
        }


        window.addEventListener('resize', debouncedResize);

        return () => {
            if (resizeObserverRef.current && container) {
                try {
                    resizeObserverRef.current.unobserve(container);
                    resizeObserverRef.current.disconnect();
                } catch (error) {
                    console.warn("Error cleaning up ResizeObserver:", error);
                }
                resizeObserverRef.current = null;
            }
            window.removeEventListener('resize', debouncedResize);
            if (resizeTimeoutRef.current) {
                clearTimeout(resizeTimeoutRef.current);
            }
        };
    }, [debouncedResize]);

    return (
        <div
            ref={containerRef}
            style={{
                width: '1000px',
                height: '100%',
                minHeight: '500px',
                position: 'relative',
                overflow: 'hidden'
            }}
        />
    );
}


function SimulationControlPanel({
                                    onStart, onNextDay, onReset,
                                    isSimulating,
                                    startDate, setStartDate,
                                    endDate, setEndDate,
                                    stockSymbol, setStockSymbol,
                                    granularity, setGranularity,
                                    isLoading
                                }) {
    return (
        <Paper elevation={2} sx={{ p: { xs: 1, sm: 1.5 }, mb: 1 }}>
            <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
                Simulation Setup
            </Typography>
            <Grid container spacing={1} alignItems="center">
                <Grid item xs={6} sm={2}>
                    <TextField
                        fullWidth
                        label="Symbol"
                        variant="outlined"
                        size="small"
                        value={stockSymbol}
                        onChange={(e) => setStockSymbol(e.target.value.toUpperCase())}
                        disabled={isSimulating || isLoading}
                        sx={{ '& .MuiInputLabel-root': { fontSize: { xs: '0.875rem', sm: '1rem' } } }}
                    />
                </Grid>
                <Grid item xs={6} sm={2}>
                    <FormControl fullWidth size="small" disabled={isSimulating || isLoading}>
                        <InputLabel sx={{ fontSize: { xs: '0.875rem', sm: '1rem' } }}>Interval</InputLabel>
                        <Select
                            label="Interval"
                            value={granularity}
                            onChange={(e) => setGranularity(e.target.value)}
                            sx={{ fontSize: { xs: '0.875rem', sm: '1rem' } }}
                        >
                            <MenuItem value="1d">Daily</MenuItem>
                            <MenuItem value="1h">1 Hour</MenuItem>
                            <MenuItem value="30m">30 Minutes</MenuItem>
                            <MenuItem value="15m">15 Minutes</MenuItem>
                            <MenuItem value="5m">5 Minutes</MenuItem>
                            <MenuItem value="1m">1 Minute</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
                <Grid item xs={6} sm={3}>
                    <TextField
                        fullWidth
                        label="Start Date"
                        type="date"
                        variant="outlined"
                        size="small"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        disabled={isSimulating || isLoading}
                        InputLabelProps={{ shrink: true }}
                        sx={{ '& .MuiInputLabel-root': { fontSize: { xs: '0.875rem', sm: '1rem' } } }}
                    />
                </Grid>
                <Grid item xs={6} sm={3}>
                    <TextField
                        fullWidth
                        label="End Date"
                        type="date"
                        variant="outlined"
                        size="small"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        disabled={isSimulating || isLoading}
                        InputLabelProps={{ shrink: true }}
                        sx={{ '& .MuiInputLabel-root': { fontSize: { xs: '0.875rem', sm: '1rem' } } }}
                    />
                </Grid>
                <Grid item xs={12} sm={2}>
                    {!isSimulating ? (
                        <Button
                            fullWidth
                            variant="contained"
                            color="primary"
                            onClick={onStart}
                            startIcon={isLoading ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
                            disabled={isLoading}
                            size="medium"
                            sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
                        >
                            {isLoading ? "Loading..." : "Start"}
                        </Button>
                    ) : (
                        <Box display="flex" gap={0.5} sx={{ width: '100%' }}>
                            <Button
                                fullWidth
                                variant="contained"
                                color="secondary"
                                onClick={onNextDay}
                                startIcon={<SkipNextIcon />}
                                size="small"
                                sx={{ fontSize: '0.75rem', flex: 1 }}
                            >
                                Next
                            </Button>
                            <Button
                                fullWidth
                                variant="outlined"
                                color="warning"
                                onClick={onReset}
                                startIcon={<ReplayIcon />}
                                size="small"
                                sx={{ fontSize: '0.75rem', flex: 1 }}
                            >
                                Reset
                            </Button>
                        </Box>
                    )}
                </Grid>
            </Grid>
        </Paper>
    );
}


function SimulationTradingPanel({
                                    stockSymbol, currentSimulatedPrice,
                                    simulatedCash, simulatedPosition,
                                    onSimulatedTrade, isSimulating
                                }) {
    const [orderType, setOrderType] = useState('MARKET');
    const [side, setSide] = useState('BUY');
    const [quantity, setQuantity] = useState('');
    const [limitPrice, setLimitPrice] = useState('');
    const [message, setMessage] = useState({ text: '', type: '' });

    useEffect(() => {
        if (orderType === 'LIMIT' && !limitPrice && currentSimulatedPrice) {
            setLimitPrice(currentSimulatedPrice.toFixed(2));
        }
        if (orderType === 'MARKET' && currentSimulatedPrice) {
            setLimitPrice(currentSimulatedPrice.toFixed(2));
        }
    }, [currentSimulatedPrice, orderType, limitPrice]);

    const handlePlaceOrder = (e) => {
        e.preventDefault();
        if (!isSimulating) {
            setMessage({ text: "Start simulation to trade.", type: 'error' });
            return;
        }

        const numQuantity = parseInt(quantity);
        if (!numQuantity || numQuantity <= 0) {
            setMessage({ text: 'Valid quantity needed.', type: 'error' });
            return;
        }

        let tradePrice;
        if (orderType === 'MARKET') {
            if (!currentSimulatedPrice) {
                setMessage({ text: 'Market price unavailable.', type: 'error' });
                return;
            }
            tradePrice = currentSimulatedPrice;
        } else {
            const numLimitPrice = parseFloat(limitPrice);
            if (!numLimitPrice || numLimitPrice <= 0) {
                setMessage({ text: 'Valid limit price needed.', type: 'error' });
                return;
            }
            tradePrice = numLimitPrice;
        }

        if (side === 'BUY') {
            const cost = numQuantity * tradePrice;
            if (simulatedCash < cost) {
                setMessage({ text: `Insufficient cash. Need $${cost.toFixed(2)}`, type: 'error' });
                return;
            }
        } else {
            if (simulatedPosition < numQuantity) {
                setMessage({ text: `Insufficient shares. Have ${simulatedPosition}`, type: 'error' });
                return;
            }
        }

        onSimulatedTrade({
            symbol: stockSymbol,
            side: side.toLowerCase(),
            type: orderType.toLowerCase(),
            quantity: numQuantity,
            price: tradePrice,
            date: currentSimulatedPrice && currentSimulatedPrice.time
                ? new Date(currentSimulatedPrice.time * 1000).toISOString()
                : new Date().toISOString()
        });

        setMessage({ text: `${side} ${numQuantity} ${stockSymbol} @ $${tradePrice.toFixed(2)}`, type: 'success' });
        setQuantity('');
        setTimeout(() => setMessage({ text: '', type: '' }), 3000);
    };

    const handleQuickSetQuantity = (percentage) => {
        let qtyToSet = '';
        if (side === 'SELL' && simulatedPosition > 0) {
            qtyToSet = Math.floor(simulatedPosition * percentage);
        } else if (side === 'BUY' && currentSimulatedPrice > 0 && simulatedCash > 0) {
            const maxAffordableShares = Math.floor(simulatedCash / currentSimulatedPrice);
            qtyToSet = Math.floor(maxAffordableShares * percentage);
        }
        setQuantity(qtyToSet > 0 ? qtyToSet.toString() : '');
    };

    return (
        <Paper elevation={3} sx={{ p: { xs: 1, sm: 1.5 }, display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" gutterBottom sx={{
                borderBottom: 1,
                borderColor: 'divider',
                pb: 0.5,
                mb: 1,
                fontSize: { xs: '1rem', sm: '1.25rem' }
            }}>
                Paper Trade: {stockSymbol}
            </Typography>

            {message.text && (
                <Alert
                    severity={message.type}
                    sx={{ mb: 1, fontSize: '0.75rem', py: 0 }}
                    onClose={() => setMessage({ text: '', type: '' })}
                >
                    {message.text}
                </Alert>
            )}

            <Box component="form" onSubmit={handlePlaceOrder} sx={{display: 'flex', flexDirection: 'column', gap: 1 }}>
                <ButtonGroup fullWidth size="small">
                    <Button
                        variant={side === 'BUY' ? 'contained' : 'outlined'}
                        color="success"
                        onClick={() => setSide('BUY')}
                        startIcon={<TrendingUpIcon />}
                        sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
                    >
                        Buy
                    </Button>
                    <Button
                        variant={side === 'SELL' ? 'contained' : 'outlined'}
                        color="error"
                        onClick={() => setSide('SELL')}
                        startIcon={<TrendingDownIcon />}
                        sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
                    >
                        Sell
                    </Button>
                </ButtonGroup>

                <FormControl fullWidth size="small">
                    <InputLabel sx={{ fontSize: { xs: '0.875rem', sm: '1rem' } }}>Order Type</InputLabel>
                    <Select
                        label="Order Type"
                        value={orderType}
                        onChange={(e) => setOrderType(e.target.value)}
                        sx={{ fontSize: { xs: '0.875rem', sm: '1rem' } }}
                    >
                        <MenuItem value="MARKET">Market</MenuItem>
                        <MenuItem value="LIMIT">Limit</MenuItem>
                    </Select>
                </FormControl>

                {orderType === 'LIMIT' && (
                    <TextField
                        fullWidth
                        label="Limit Price"
                        type="number"
                        size="small"
                        value={limitPrice}
                        onChange={(e) => setLimitPrice(e.target.value)}
                        InputProps={{ inputProps: { min: 0.01, step: 0.01 } }}
                        sx={{ '& .MuiInputLabel-root': { fontSize: { xs: '0.875rem', sm: '1rem' } } }}
                        required
                    />
                )}

                <TextField
                    fullWidth
                    label="Quantity"
                    type="number"
                    size="small"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    InputProps={{ inputProps: { min: 1, step: 1 } }}
                    sx={{ '& .MuiInputLabel-root': { fontSize: { xs: '0.875rem', sm: '1rem' } } }}
                    required
                />

                <Box sx={{ display: 'flex', gap: 0.5 }}>
                    {[0.25, 0.50, 0.75, 1.0].map(perc => (
                        <Button
                            key={perc}
                            size="small"
                            variant="text"
                            sx={{ p: 0.5, minWidth: 'auto', fontSize: '0.65rem', flex: 1 }}
                            onClick={() => handleQuickSetQuantity(perc)}
                        >
                            {perc * 100}%
                        </Button>
                    ))}
                </Box>

                <Button
                    fullWidth
                    variant="contained"
                    type="submit"
                    disabled={!isSimulating}
                    color={side === 'BUY' ? "success" : "error"}
                    sx={{ mt: 'auto', py: 1, fontWeight: 'bold', fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
                >
                    Submit Paper Trade
                </Button>
            </Box>

            <Box sx={{ mt: 1, pt: 1, borderTop: 1, borderColor: 'divider' }}>
                <Typography variant="subtitle2" sx={{ mb: 0.5, fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                    Portfolio
                </Typography>
                <Grid container spacing={1} sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>
                    <Grid item xs={4}>
                        <Typography variant="caption" display="block">Cash:</Typography>
                        <Typography variant="body2" sx={{ fontSize: 'inherit', fontWeight: 'bold' }}>
                            ${simulatedCash.toFixed(0)}
                        </Typography>
                    </Grid>
                    <Grid item xs={4}>
                        <Typography variant="caption" display="block">Shares:</Typography>
                        <Typography variant="body2" sx={{ fontSize: 'inherit', fontWeight: 'bold' }}>
                            {simulatedPosition}
                        </Typography>
                    </Grid>
                    <Grid item xs={4}>
                        <Typography variant="caption" display="block">Price:</Typography>
                        <Typography variant="body2" sx={{ fontSize: 'inherit', fontWeight: 'bold' }}>
                            {currentSimulatedPrice ? `$${currentSimulatedPrice.toFixed(2)}` : 'N/A'}
                        </Typography>
                    </Grid>
                </Grid>
            </Box>
        </Paper>
    );
}

function SimulationTradeLogPanel({ simulatedTrades }) {
    return (
        <Paper elevation={3} sx={{ p: 2, mt: 2, height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
            <Typography variant="h6" gutterBottom>Trade Log</Typography>
            <Box sx={{ flex: 1, overflowY: 'auto' }}>
                {simulatedTrades.length > 0 ? (
                    simulatedTrades.slice().reverse().map(trade => (
                        <Typography key={trade.id} variant="body2" sx={{ mb: 1 }}>
                            {new Date(trade.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })} - {trade.side.toUpperCase()} {trade.quantity} {trade.symbol} @ ${trade.price.toFixed(2)}
                        </Typography>
                    ))
                ) : (
                    <Typography variant="body2">No trades yet.</Typography>
                )}
            </Box>
        </Paper>
    );
}


export default function SimulationPage() {

    const [stockSymbol, setStockSymbol] = useState("");
    const today = new Date();
    const yesterday = new Date(new Date().setDate(today.getDate() - 1));
    const oneMonthAgo = new Date(new Date().setMonth(today.getMonth() - 1));

    const [simStartDate, setSimStartDate] = useState(formatDateForAPI(oneMonthAgo));
    const [simEndDate, setSimEndDate] = useState(formatDateForAPI(yesterday));
    const [granularity, setGranularity] = useState("1d");

    const [isSimulating, setIsSimulating] = useState(false);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const [allHistoricalData, setAllHistoricalData] = useState([]);
    const [currentSimDataIndex, setCurrentSimDataIndex] = useState(-1);

    const [chartDisplayData, setChartDisplayData] = useState([]);
    const [currentSimulatedDayData, setCurrentSimulatedDayData] = useState(null);

    const [simulatedCash, setSimulatedCash] = useState(100000);
    const [simulatedPositions, setSimulatedPositions] = useState({});
    const [simulatedTrades, setSimulatedTrades] = useState([]);

    const chartKey = useRef(0);

    const handleStartSimulation = async () => {
        if (!stockSymbol || !simStartDate || !simEndDate || !granularity) {
            alert("Please select a stock symbol, granularity, and a valid date range.");
            return;
        }
        if (new Date(simStartDate) >= new Date(simEndDate)) {
            alert("Start date must be before end date.");
            return;
        }
        setIsLoadingHistory(true);
        try {

            const historyUrl = `${API_BASE_URL_MARKET_DATA}/history/${stockSymbol}/${simStartDate}/${simEndDate}/${granularity}`;
            const response = await fetch(historyUrl);
            if (!response.ok) throw new Error(`Failed to fetch history: ${response.status}`);
            const fullHistory = await response.json();

            if (!fullHistory || fullHistory.length === 0) {
                alert("No historical data found for the selected range and symbol.");
                setIsLoadingHistory(false);
                return;
            }

            setAllHistoricalData(fullHistory);
            setCurrentSimDataIndex(0);
            setChartDisplayData([fullHistory[0]]);
            setCurrentSimulatedDayData(fullHistory[0]);

            setSimulatedCash(100000);
            setSimulatedPositions({ [stockSymbol]: 0 });
            setSimulatedTrades([]);

            setIsSimulating(true);
            chartKey.current += 1;
        } catch (error) {
            console.error("Error starting simulation:", error);
            alert(`Failed to start simulation: ${error.message}`);
        } finally {
            setIsLoadingHistory(false);
        }
    };

    const handleNextDay = () => {
        if (currentSimDataIndex < allHistoricalData.length - 1) {
            const nextIndex = currentSimDataIndex + 1;
            setCurrentSimDataIndex(nextIndex);
            setChartDisplayData(allHistoricalData.slice(0, nextIndex + 1));
            setCurrentSimulatedDayData(allHistoricalData[nextIndex]);
        } else {
            alert("End of simulation period reached. Reset to start a new simulation.");
        }
    };

    const handleResetSimulation = () => {
        setIsSimulating(false);
        setCurrentSimDataIndex(-1);
        setAllHistoricalData([]);
        setChartDisplayData([]);
        setCurrentSimulatedDayData(null);
        setSimulatedCash(100000);
        setSimulatedPositions({ [stockSymbol]: 0 });
        setSimulatedTrades([]);
        chartKey.current += 1;
    };

    const handleSimulatedTrade = (tradeDetails) => {
        const { quantity, price, side, symbol } = tradeDetails;
        const costOrProceeds = quantity * price;

        setSimulatedCash(prevCash =>
            side === 'buy' ? prevCash - costOrProceeds : prevCash + costOrProceeds
        );
        setSimulatedPositions(prevPos => ({
            ...prevPos,
            [symbol]: (prevPos[symbol] || 0) + (side === 'buy' ? quantity : -quantity)
        }));
        setSimulatedTrades(prevTrades => [
            ...prevTrades,
            { ...tradeDetails, timestamp: new Date().toISOString(), id: Date.now() + Math.random() }
        ]);
    };

    const currentPositionForSymbol = simulatedPositions[stockSymbol] || 0;
    const currentPriceForTrading = currentSimulatedDayData ? currentSimulatedDayData.close : null;

    return (
        <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <AppBar position="static" sx={{ flexShrink: 0 }}>
                <Toolbar variant="dense">
                    <Typography variant="h6" component="div" sx={{
                        flexGrow: 1,
                        fontWeight: 'bold',
                        fontSize: { xs: '1rem', sm: '1.25rem' }
                    }}>
                        Trading Simulation
                    </Typography>
                    {isSimulating && (
                        <Typography variant="subtitle2" sx={{
                            display: 'flex',
                            alignItems: 'center',
                            mr: 2,
                            fontSize: { xs: '0.75rem', sm: '0.875rem' }
                        }}>
                            <WalletIcon sx={{ mr: 0.5, fontSize: 'inherit' }} />
                            ${simulatedCash.toFixed(0)}
                        </Typography>
                    )}
                    {isSimulating && currentSimulatedDayData && (
                        <Typography variant="caption" sx={{ fontSize: { xs: '0.6rem', sm: '0.75rem' } }}>
                            {new Date(currentSimulatedDayData.time * 1000).toLocaleDateString()}
                        </Typography>
                    )}
                </Toolbar>
            </AppBar>

            <Box sx={{ flex: 1, p: { xs: 0.5, sm: 1 }, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <SimulationControlPanel
                    onStart={handleStartSimulation}
                    onNextDay={handleNextDay}
                    onReset={handleResetSimulation}
                    isSimulating={isSimulating}
                    startDate={simStartDate} setStartDate={setSimStartDate}
                    endDate={simEndDate} setEndDate={setSimEndDate}
                    stockSymbol={stockSymbol} setStockSymbol={setStockSymbol}
                    granularity={granularity} setGranularity={setGranularity}
                    isLoading={isLoadingHistory}
                />

                {isSimulating && allHistoricalData.length > 0 ? (
                    <Grid container spacing={1} sx={{ flex: 1}}>
                        <Grid item xs={12} md={8} sx={{  }}>
                            <Paper elevation={3} sx={{
                                width: '100%',
                                display: 'flex',
                                flexDirection: 'column',
                                overflow: 'hidden'
                            }}>
                                <Typography variant="body2" sx={{
                                    p: 0.5,
                                    textAlign: 'center',
                                    borderBottom: 1,
                                    borderColor: 'divider',
                                    fontSize: { xs: '0.75rem', sm: '0.875rem' }
                                }}>
                                    {stockSymbol} - {currentSimulatedDayData ?
                                    new Date(currentSimulatedDayData.time * 1000).toLocaleDateString() : 'N/A'}
                                </Typography>
                                <Box sx={{ flex: 1, minHeight: 0 }}>
                                    <SimulationLiveChart
                                        key={chartKey.current}
                                        data={chartDisplayData}
                                    />
                                </Box>
                            </Paper>
                        </Grid>
                        <Grid >
                            <SimulationTradingPanel
                                stockSymbol={stockSymbol}
                                currentSimulatedPrice={currentPriceForTrading}
                                simulatedCash={simulatedCash}
                                simulatedPosition={currentPositionForSymbol}
                                onSimulatedTrade={handleSimulatedTrade}
                                isSimulating={isSimulating}
                            />
                        </Grid>
                        <Grid>
                            <Box >
                                <SimulationTradeLogPanel simulatedTrades={simulatedTrades} />
                            </Box>
                        </Grid>
                    </Grid>
                ) : (
                    <Box sx={{
                        flex: 1,
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center'
                    }}>
                        <Typography variant="h5" sx={{ fontSize: { xs: '1.25rem', sm: '1.5rem' } }}>
                            Select symbol and date range to start simulation
                        </Typography>
                    </Box>
                )}
            </Box>
        </Box>
    );
}