/**
 * CarbonWise Chart Wrapper
 * Manages Chart.js canvas state, theme swaps, and coordinates historical/projected datasets.
 */

class CarbonWiseCharts {
    static chartInstance = null;

    /**
     * Renders a line chart displaying historical monthly carbon totals
     * together with future AI predictions.
     * 
     * @param {Array} history - Array of historical calculation documents.
     * @param {Object} predictions - Predictions object containing 30-day and 90-day keys.
     */
    static renderHistoryAndPrediction(history, predictions) {
        const ctx = document.getElementById('chart-history');
        if (!ctx) return;

        // Destroy old chart to prevent redraw rendering glitch
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }

        // Check if history is empty
        if (!history || history.length === 0) {
            console.warn("[Chart] No historical logs found for rendering.");
            return;
        }

        // Parse history in chronological order (oldest to newest)
        const chronHistory = [...history].reverse();
        
        const labels = [];
        const historicalData = [];
        const predictiveData = [];

        // Build historical datasets
        chronHistory.forEach((entry, idx) => {
            const date = new Date(entry.created_at);
            const labelStr = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
            labels.push(labelStr);
            
            const totalEmissions = entry.emissions.total;
            historicalData.push(totalEmissions);
            // Predictions match historical values until the tail to draw a continuous line
            predictiveData.push(null);
        });

        // Link predictive line to the final historical data point
        const lastHistoryIndex = historicalData.length - 1;
        predictiveData[lastHistoryIndex] = historicalData[lastHistoryIndex];

        // Append future labels & predictions
        if (predictions) {
            labels.push("+30 Days (AI)");
            predictiveData.push(predictions.projection_30_days);
            historicalData.push(null);

            labels.push("+90 Days (AI)");
            predictiveData.push(predictions.projection_90_days);
            historicalData.push(null);
        }

        // Determine theme colors based on body settings (high contrast vs standard dark)
        const isHighContrast = document.body.classList.contains('high-contrast');
        const textColor = isHighContrast ? '#ffffff' : '#9ca3af';
        const gridColor = isHighContrast ? '#ffffff' : 'rgba(75, 85, 99, 0.2)';
        const historyLineColor = isHighContrast ? '#00ff00' : '#10b981';
        const predictionLineColor = isHighContrast ? '#ffff00' : '#a855f7';

        this.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Historical Footprint (kg CO2e)',
                        data: historicalData,
                        borderColor: historyLineColor,
                        backgroundColor: 'transparent',
                        borderWidth: 3,
                        pointBackgroundColor: historyLineColor,
                        pointRadius: 4,
                        spanGaps: false
                    },
                    {
                        label: 'AI Forecast (kg CO2e)',
                        data: predictiveData,
                        borderColor: predictionLineColor,
                        backgroundColor: 'transparent',
                        borderWidth: 3,
                        borderDash: [6, 6],
                        pointBackgroundColor: predictionLineColor,
                        pointRadius: 5,
                        spanGaps: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: textColor,
                            font: {
                                family: 'Inter',
                                size: 12,
                                weight: '500'
                            }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: gridColor
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                family: 'Inter'
                            }
                        }
                    },
                    y: {
                        grid: {
                            color: gridColor
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                family: 'Inter'
                            }
                        },
                        title: {
                            display: true,
                            text: 'kg CO2e / month',
                            color: textColor,
                            font: {
                                family: 'Inter',
                                weight: '600'
                            }
                        }
                    }
                }
            }
        });
    }
}
