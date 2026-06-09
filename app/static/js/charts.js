/**
 * @fileoverview CarbonWise Chart Wrapper.
 *
 * Manages the Chart.js canvas lifecycle for the footprint history and AI
 * prediction line chart. Handles chart instance destruction and recreation on
 * each render cycle, theme-aware colour selection for high-contrast and standard
 * dark modes, and the construction of dual datasets: a solid historical line
 * and a dashed predictive forecast line.
 *
 * The chart bridges historical data (real past entries) with AI-generated future
 * projections by connecting the last historical data point to the first forecast
 * point, creating a visually continuous story of the user's carbon trajectory.
 *
 * Rendering is stateless except for the singleton {@link CarbonWiseCharts.chartInstance}
 * which is destroyed before each re-render to prevent Chart.js accumulation leaks.
 */

/**
 * Chart.js line tension value for smoother curve rendering.
 * Set to 0 for straight-line segments matching carbon data precision.
 */
const CHART_LINE_TENSION = 0;

/**
 * Border width in pixels for both the historical and forecast dataset lines.
 * @type {number}
 */
const CHART_LINE_BORDER_WIDTH = 3;

/**
 * Point radius in pixels for historical data markers.
 * @type {number}
 */
const CHART_POINT_RADIUS_HISTORY = 4;

/**
 * Point radius in pixels for AI forecast markers (slightly larger for distinction).
 * @type {number}
 */
const CHART_POINT_RADIUS_FORECAST = 5;

/**
 * Dash pattern [on, off] in pixels for the AI forecast dashed line.
 * @type {Array<number>}
 */
const CHART_DASH_PATTERN = [6, 6];

/**
 * Font family applied to all chart labels and titles.
 * Must match the Google Fonts import in index.html.
 * @type {string}
 */
const CHART_FONT_FAMILY = 'Inter';

class CarbonWiseCharts {
    /**
     * The active Chart.js instance, or {@code null} when no chart has been rendered.
     * Stored as a class property so it can be destroyed before each re-render.
     * @type {Chart|null}
     */
    static chartInstance = null;

    /**
     * Render a dual-line chart combining historical footprint records with
     * AI-generated 30-day and 90-day predictions.
     *
     * Destroys the existing Chart.js instance before creating a new one to
     * prevent ghost canvas layers from accumulating across re-renders triggered
     * by contrast mode toggles or simulator interactions.
     *
     * The two datasets share a continuous visual connection: the predictive line
     * inherits the last historical value as its starting point, so the transition
     * from real data to forecast feels seamless to the user.
     *
     * Colour selection adapts to the active display mode:
     *  - Standard dark mode: green historical line, purple forecast line.
     *  - High-contrast mode: bright green historical line, yellow forecast line.
     *
     * @param {Array<Object>} history - Historical calculation documents ordered
     *   newest-first. Each entry must contain {@code created_at} (ISO string) and
     *   {@code emissions.total} (number in kg CO2e).
     * @param {Object|null} predictions - AI forecast object containing
     *   {@code projection_30_days} and {@code projection_90_days} numbers,
     *   or {@code null} when no prediction is available.
     * @returns {void}
     */
    static renderHistoryAndPrediction(history, predictions) {
        const ctx = document.getElementById('chart-history');
        if (!ctx) return;

        // Destroy the previous chart instance to prevent canvas accumulation
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }

        if (!history || history.length === 0) {
            console.warn("[Chart] No historical logs found for rendering.");
            return;
        }

        // Reverse to chronological order so the chart reads left (oldest) to right (newest)
        const chronHistory = [...history].reverse();

        const labels = [];
        const historicalData = [];
        const predictiveData = [];

        // Build the historical dataset; predictive slots remain null until the tail
        chronHistory.forEach((entry) => {
            const date = new Date(entry.created_at);
            const labelStr = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
            labels.push(labelStr);
            historicalData.push(entry.emissions.total);
            predictiveData.push(null); // Placeholder — filled below for the tail point
        });

        // Link the forecast line to the last real data point for visual continuity
        const lastHistoryIndex = historicalData.length - 1;
        predictiveData[lastHistoryIndex] = historicalData[lastHistoryIndex];

        // Append future labels and AI projection values when available
        if (predictions) {
            labels.push("+30 Days (AI)");
            predictiveData.push(predictions.projection_30_days);
            historicalData.push(null);

            labels.push("+90 Days (AI)");
            predictiveData.push(predictions.projection_90_days);
            historicalData.push(null);
        }

        // Select theme-aware colours — high-contrast uses maximum-luminance colours
        // to meet WCAG AA contrast requirements against the dark background
        const themeColors = _getThemeColors();

        this.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Historical Footprint (kg CO2e)',
                        data: historicalData,
                        borderColor: themeColors.historyLine,
                        backgroundColor: 'transparent',
                        borderWidth: CHART_LINE_BORDER_WIDTH,
                        pointBackgroundColor: themeColors.historyLine,
                        pointRadius: CHART_POINT_RADIUS_HISTORY,
                        spanGaps: false,
                    },
                    {
                        label: 'AI Forecast (kg CO2e)',
                        data: predictiveData,
                        borderColor: themeColors.predictionLine,
                        backgroundColor: 'transparent',
                        borderWidth: CHART_LINE_BORDER_WIDTH,
                        borderDash: CHART_DASH_PATTERN,
                        pointBackgroundColor: themeColors.predictionLine,
                        pointRadius: CHART_POINT_RADIUS_FORECAST,
                        spanGaps: false,
                    }
                ]
            },
            options: _buildChartOptions(themeColors),
        });
    }
}

// ── Private Helpers ──────────────────────────────────────────────────────────

/**
 * Return theme-aware colour values based on the current display mode.
 *
 * Reads the {@code "high-contrast"} class on {@code document.body} to decide
 * between maximum-luminance high-contrast colours and the default dark-mode palette.
 *
 * @returns {{textColor: string, gridColor: string, historyLine: string, predictionLine: string}}
 *   Object containing four colour strings for text, grid lines, and each dataset.
 */
function _getThemeColors() {
    const isHighContrast = document.body.classList.contains('high-contrast');
    return {
        textColor: isHighContrast ? '#ffffff' : '#9ca3af',
        gridColor: isHighContrast ? '#ffffff' : 'rgba(75, 85, 99, 0.2)',
        historyLine: isHighContrast ? '#00ff00' : '#10b981',
        predictionLine: isHighContrast ? '#ffff00' : '#a855f7',
    };
}

/**
 * Build the Chart.js options configuration object with consistent axis styles.
 *
 * Extracts option construction into a pure function to keep
 * {@link CarbonWiseCharts.renderHistoryAndPrediction} readable and testable.
 *
 * @param {{textColor: string, gridColor: string}} themeColors - Theme colour values
 *   as returned by {@link _getThemeColors}.
 * @returns {Object} Chart.js {@code options} configuration object.
 */
function _buildChartOptions(themeColors) {
    const { textColor, gridColor } = themeColors;
    const fontConfig = { family: CHART_FONT_FAMILY };
    const axisTicks = { color: textColor, font: fontConfig };
    const axisGrid = { color: gridColor };

    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: textColor,
                    font: { family: CHART_FONT_FAMILY, size: 12, weight: '500' },
                }
            },
            tooltip: {
                // Index mode shows both dataset values for a given x-axis label
                mode: 'index',
                intersect: false,
            }
        },
        scales: {
            x: { grid: axisGrid, ticks: axisTicks },
            y: {
                grid: axisGrid,
                ticks: axisTicks,
                title: {
                    display: true,
                    text: 'kg CO2e / month',
                    color: textColor,
                    font: { family: CHART_FONT_FAMILY, weight: '600' },
                }
            }
        }
    };
}
