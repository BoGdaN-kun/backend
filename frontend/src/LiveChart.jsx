import React, { useEffect, useRef, useCallback } from 'react';
import * as LightweightCharts from 'lightweight-charts';

export default function LiveChartLW({
                                        symbol = 'AAPL',

                                        bootstrapEndpoint = 'http://localhost:8000/today',

                                        pollEndpoint = 'http://localhost:8000/candles?limit=5',
                                        pollMs = 2000, // Poll every 2 seconds
                                        height = 400,
                                    }) {
    const containerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const pollingTimerRef = useRef(null);

    const toLWFormat = useCallback(c => ({
        time: c.time,
        open: parseFloat(c.open),
        high: parseFloat(c.high),
        low: parseFloat(c.low),
        close: parseFloat(c.close),
    }), []);

    useEffect(() => {
        if (!containerRef.current) return;

        const chart = LightweightCharts.createChart(containerRef.current, {
            height,
            layout: {
                textColor: '#333',
                background: { type: LightweightCharts.ColorType.Solid, color: '#fff' }
            },
            grid: { horzLines: { visible: false }, vertLines: { visible: false } },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#D1D4DC',
            },
            rightPriceScale: {
                borderColor: '#D1D4DC',
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
        });
        chartRef.current = chart;


        if (LightweightCharts.CandlestickSeries) {
            const candleSeries = chart.addSeries(
                LightweightCharts.CandlestickSeries,
                {
                    upColor: '#26a69a',
                    downColor: '#ef5350',
                    wickUpColor: '#26a69a',
                    wickDownColor: '#ef5350',
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
            if (!seriesRef.current) return;
            try {
                const response = await fetch(bootstrapEndpoint, { cache: 'no-store' });
                if (!response.ok) {
                    throw new Error(`Bootstrap HTTP error! status: ${response.status} - ${await response.text()}`);
                }
                const data = (await response.json()).map(toLWFormat);
                if (isMounted && seriesRef.current) {
                    seriesRef.current.setData(data);

                }
            } catch (err) {
                console.error('Bootstrap data error:', err);
            }
        };

        const pollData = async () => {
            if (!seriesRef.current) return;
            try {
                const response = await fetch(pollEndpoint, { cache: 'no-store' });
                if (!response.ok) {
                    throw new Error(`Polling HTTP error! status: ${response.status} - ${await response.text()}`);
                }
                const liveCandles = (await response.json()).map(toLWFormat);
                if (isMounted && seriesRef.current && liveCandles.length > 0) {
                    liveCandles.forEach(candle => {

                        seriesRef.current.update(candle);
                    });

                    if (chartRef.current && !chartRef.current.timeScale().options().secondsVisible) {
                        chartRef.current.timeScale().applyOptions({ secondsVisible: true });
                    }
                }
            } catch (err) {
                console.error('Polling data error:', err);
            }
        };

        bootstrapData().then(() => {
            if (isMounted) {
                pollData();
                pollingTimerRef.current = setInterval(pollData, pollMs);
            }
        });

        return () => {
            isMounted = false;
            clearInterval(pollingTimerRef.current);
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
        };
    }, [bootstrapEndpoint, pollEndpoint, pollMs, height, toLWFormat, symbol]);

    useEffect(() => {
        const chart = chartRef.current;
        if (!chart) return;
        const handleResize = () => {
            if (containerRef.current && chartRef.current ) {
                chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
            }
        };
        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
        };
    }, []);

    return <div ref={containerRef} style={{ width: '100%', height: `${height}px` }} />;
}

