/**
 * @fileoverview CarbonWise Main Application Controller.
 *
 * Bootstraps the single-page application, manages shared client state,
 * routes between the authentication and dashboard views, and wires all
 * user interaction event listeners. Delegates DOM manipulation to
 * {@link CarbonWiseUI}, network calls to {@link CarbonWiseAPI}, and chart
 * rendering to {@link CarbonWiseCharts}.
 *
 * Module responsibilities:
 *  - One-time initialisation of DOM cache, accessibility controls, and listeners.
 *  - Session check on load — redirect to dashboard if already authenticated.
 *  - Orchestration of the full dashboard data-loading sequence.
 *  - Simulator debounce, coach refresh, and goal completion handlers.
 *
 * Constants sourced from {@link app/constants.py}:
 *  - {@code SIMULATOR_DEBOUNCE_MS} = 250 — anti-flooding delay on sliders.
 *  - {@code GOAL_CARBON_HIGH_IMPACT} = 25, MEDIUM = 12, LOW = 5 — savings estimates.
 */

// ── Shared Client State ─────────────────────────────────────────────────────

/** @type {Object|null} Authenticated user profile document from the server. */
let currentUser = null;

/** @type {Object|null} Most recent calculation document for simulator use. */
let latestCalculation = null;

/** @type {Object} Current action plan data keyed by schedule type. */
let currentActionPlan = {};

/** @type {string} Currently active plan schedule tab identifier. */
let activePlanTab = 'daily';

// ── UI Badge Config (mirrors backend BADGE_CONFIGS constant) ─────────────────

/**
 * Badge display configuration duplicated from the server constants for
 * client-side rendering. Must stay in sync with {@code app/constants.py}.
 * @type {Object.<string, {title: string, description: string, icon: string}>}
 */
const BADGE_CONFIGS = {
    "transit_hero": {
        "title": "Transit Pioneer",
        "description": "Utilize public transit or electric vehicles for at least 80% of travel.",
        "icon": "bus-front-fill"
    },
    "green_diet": {
        "title": "Meatless Maestro",
        "description": "Adopt a vegetarian or vegan lifestyle for lower carbon food footprint.",
        "icon": "egg-fried"
    },
    "energy_wizard": {
        "title": "Eco-Volt",
        "description": "Transition home electricity usage to clean/solar sources.",
        "icon": "lightning-charge-fill"
    },
    "eco_warrior": {
        "title": "Eco Warrior",
        "description": "Achieve a total Eco Score of 85 or above.",
        "icon": "shield-check"
    },
    "streak_master": {
        "title": "Habit Builder",
        "description": "Maintain a calculation or goal streak of 7 days or more.",
        "icon": "fire"
    }
};

// ── DOM Cache ────────────────────────────────────────────────────────────────

/**
 * Centralised DOM reference cache — eliminates repeated {@code getElementById}
 * queries across event handlers. All references are populated once during
 * {@link DOM.init} and reused for the lifetime of the page.
 *
 * @namespace DOM
 */
const DOM = {
    viewAuth: null,
    viewDashboard: null,
    userGreeting: null,
    streakValue: null,
    contrastBtn: null,
    motionBtn: null,
    fontInc: null,
    fontDec: null,
    fontReset: null,
    tabLogin: null,
    tabRegister: null,
    panelLogin: null,
    panelRegister: null,
    formRegister: null,
    regUsername: null,
    regEmail: null,
    regPassword: null,
    errRegUsername: null,
    errRegEmail: null,
    errRegPassword: null,
    formLogin: null,
    loginEmail: null,
    loginPassword: null,
    errLoginEmail: null,
    errLoginPassword: null,
    btnLogout: null,
    formCalculator: null,
    btnRefreshCoach: null,
    predictionPanel: null,
    predictionText: null,
    coachLoader: null,
    coachPanel: null,

    // Calculator inputs
    calcGasCar: null,
    calcElectricCar: null,
    calcTransit: null,
    calcFlight: null,
    calcGridKwh: null,
    calcCleanKwh: null,
    calcDiet: null,
    calcShopping: null,

    // Simulator controls and labels
    simTransit: null,
    simDiet: null,
    simEnergy: null,
    simTransitLbl: null,
    simDietLbl: null,
    simEnergyLbl: null,
    simProjected: null,
    simReduction: null,
    simScore: null,

    /**
     * Populate all DOM references from the live document.
     * Must be called once after {@code DOMContentLoaded} fires.
     *
     * @returns {void}
     */
    init() {
        this.viewAuth = document.getElementById('view-auth');
        this.viewDashboard = document.getElementById('view-dashboard');
        this.userGreeting = document.getElementById('user-greeting');
        this.streakValue = document.getElementById('lbl-streak-value');
        this.contrastBtn = document.getElementById('btn-toggle-contrast');
        this.motionBtn = document.getElementById('btn-toggle-motion');
        this.fontInc = document.getElementById('btn-font-inc');
        this.fontDec = document.getElementById('btn-font-dec');
        this.fontReset = document.getElementById('btn-font-reset');
        this.tabLogin = document.getElementById('tab-login');
        this.tabRegister = document.getElementById('tab-register');
        this.panelLogin = document.getElementById('panel-login');
        this.panelRegister = document.getElementById('panel-register');
        this.formRegister = document.getElementById('form-register');
        this.regUsername = document.getElementById('reg-username');
        this.regEmail = document.getElementById('reg-email');
        this.regPassword = document.getElementById('reg-password');
        this.errRegUsername = document.getElementById('err-reg-username');
        this.errRegEmail = document.getElementById('err-reg-email');
        this.errRegPassword = document.getElementById('err-reg-password');
        this.formLogin = document.getElementById('form-login');
        this.loginEmail = document.getElementById('login-email');
        this.loginPassword = document.getElementById('login-password');
        this.errLoginEmail = document.getElementById('err-login-email');
        this.errLoginPassword = document.getElementById('err-login-password');
        this.btnLogout = document.getElementById('btn-logout');
        this.formCalculator = document.getElementById('form-calculator');
        this.btnRefreshCoach = document.getElementById('btn-refresh-coach');
        this.predictionPanel = document.getElementById('prediction-panel');
        this.predictionText = document.getElementById('lbl-prediction-text');
        this.coachLoader = document.getElementById('coach-insights-loading');
        this.coachPanel = document.getElementById('coach-content-panel');

        this.calcGasCar = document.getElementById('calc-gas-car');
        this.calcElectricCar = document.getElementById('calc-electric-car');
        this.calcTransit = document.getElementById('calc-transit');
        this.calcFlight = document.getElementById('calc-flight');
        this.calcGridKwh = document.getElementById('calc-grid-kwh');
        this.calcCleanKwh = document.getElementById('calc-clean-kwh');
        this.calcDiet = document.getElementById('calc-diet');
        this.calcShopping = document.getElementById('calc-shopping');

        this.simTransit = document.getElementById('sim-transit');
        this.simDiet = document.getElementById('sim-diet');
        this.simEnergy = document.getElementById('sim-energy');
        this.simTransitLbl = document.getElementById('lbl-sim-transit');
        this.simDietLbl = document.getElementById('lbl-sim-diet');
        this.simEnergyLbl = document.getElementById('lbl-sim-energy');
        this.simProjected = document.getElementById('lbl-sim-projected');
        this.simReduction = document.getElementById('lbl-sim-reduction');
        this.simScore = document.getElementById('lbl-sim-score');
    }
};

// ── Application Constants ────────────────────────────────────────────────────

/** Debounce delay in ms for simulator API calls (mirrors SIMULATOR_DEBOUNCE_MS). */
const SIMULATOR_DEBOUNCE_MS = 250;

/** Font size step percentage per button press (mirrors FONT_SIZE_STEP_PCT). */
const FONT_SIZE_STEP_PCT = 10;

/** Maximum font size as a percentage of default (mirrors FONT_SIZE_MAX_PCT). */
const FONT_SIZE_MAX_PCT = 140;

/** Minimum font size as a percentage of default (mirrors FONT_SIZE_MIN_PCT). */
const FONT_SIZE_MIN_PCT = 80;

/** Default font size percentage (mirrors FONT_SIZE_DEFAULT_PCT). */
const FONT_SIZE_DEFAULT_PCT = 100;

/** Estimated carbon saved for completing a high-impact goal (kg CO2e). */
const GOAL_CARBON_HIGH_IMPACT = 25.0;

/** Estimated carbon saved for completing a medium-impact goal (kg CO2e). */
const GOAL_CARBON_MEDIUM_IMPACT = 12.0;

/** Estimated carbon saved for completing a low-impact goal (kg CO2e). */
const GOAL_CARBON_LOW_IMPACT = 5.0;

// ── Initialisation ───────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

/**
 * Bootstrap the application: initialise DOM cache, attach event listeners,
 * and check whether the user already has an active session.
 *
 * Runs once after the DOM is fully parsed. Redirects to the dashboard view
 * immediately when an authenticated session cookie is detected.
 *
 * @async
 * @returns {Promise<void>}
 */
async function initApp() {
    DOM.init();
    CarbonWiseUI.initDOM();
    setupAccessibilityControls();
    setupAuthListeners();
    setupDashboardListeners();
    setupSimulatorListeners();

    // Attempt session validation — if the cookie is still live the server
    // will return the profile and we can skip the login screen entirely
    try {
        const response = await CarbonWiseAPI.getProfile();
        if (response && response.data) {
            handleLoginSuccess(response.data);
        } else {
            showAuthView();
        }
    } catch (e) {
        // 401 expected when no session exists — show auth view silently
        showAuthView();
    }
}

// ── View Controllers ─────────────────────────────────────────────────────────

/**
 * Display the authentication panel and hide the dashboard.
 *
 * @returns {void}
 */
function showAuthView() {
    DOM.viewAuth.classList.remove('hidden');
    DOM.viewDashboard.classList.add('hidden');
    DOM.userGreeting.textContent = 'Welcome, Guest';
}

/**
 * Display the dashboard and hide the authentication panel.
 * Updates the greeting label with the authenticated user's display name.
 *
 * @returns {void}
 */
function showDashboardView() {
    DOM.viewAuth.classList.add('hidden');
    DOM.viewDashboard.classList.remove('hidden');
    if (currentUser) {
        DOM.userGreeting.textContent = `Welcome, ${currentUser.username}`;
    }
}

// ── Accessibility Controls ───────────────────────────────────────────────────

/**
 * Attach accessibility preference controls and restore saved preferences from
 * {@code localStorage} on page load.
 *
 * Handles:
 *  - High-contrast mode toggle (persisted as {@code "contrast"}).
 *  - Reduced-motion mode toggle (persisted as {@code "motion"}).
 *  - Font size increase / decrease / reset (persisted as {@code "fontSizePct"}).
 *
 * @returns {void}
 */
function setupAccessibilityControls() {
    // Restore high-contrast preference from a previous session
    if (localStorage.getItem('contrast') === 'enabled') {
        document.body.classList.add('high-contrast');
        DOM.contrastBtn.setAttribute('aria-pressed', 'true');
    }

    // Restore reduced-motion preference from a previous session
    if (localStorage.getItem('motion') === 'reduced') {
        document.body.classList.add('reduced-motion');
        DOM.motionBtn.setAttribute('aria-pressed', 'true');
    }

    // Restore font-size preference — default to 100% when absent
    let fontSizePct = parseInt(localStorage.getItem('fontSizePct')) || FONT_SIZE_DEFAULT_PCT;
    document.documentElement.style.fontSize = `${fontSizePct}%`;

    DOM.contrastBtn.addEventListener('click', () => {
        const active = document.body.classList.toggle('high-contrast');
        DOM.contrastBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
        localStorage.setItem('contrast', active ? 'enabled' : 'disabled');
        CarbonWiseUI.announce(`High contrast mode ${active ? 'enabled' : 'disabled'}.`);

        // Re-render chart with updated theme colours after toggling contrast
        if (latestCalculation) {
            loadChartAndPredictions();
        }
    });

    DOM.motionBtn.addEventListener('click', () => {
        const active = document.body.classList.toggle('reduced-motion');
        DOM.motionBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
        localStorage.setItem('motion', active ? 'reduced' : 'normal');
        CarbonWiseUI.announce(`Reduced motion mode ${active ? 'enabled' : 'disabled'}.`);
    });

    DOM.fontInc.addEventListener('click', () => {
        if (fontSizePct < FONT_SIZE_MAX_PCT) {
            fontSizePct += FONT_SIZE_STEP_PCT;
            document.documentElement.style.fontSize = `${fontSizePct}%`;
            localStorage.setItem('fontSizePct', fontSizePct);
            CarbonWiseUI.announce(`Text size increased to ${fontSizePct} percent.`);
        }
    });

    DOM.fontDec.addEventListener('click', () => {
        if (fontSizePct > FONT_SIZE_MIN_PCT) {
            fontSizePct -= FONT_SIZE_STEP_PCT;
            document.documentElement.style.fontSize = `${fontSizePct}%`;
            localStorage.setItem('fontSizePct', fontSizePct);
            CarbonWiseUI.announce(`Text size decreased to ${fontSizePct} percent.`);
        }
    });

    DOM.fontReset.addEventListener('click', () => {
        fontSizePct = FONT_SIZE_DEFAULT_PCT;
        document.documentElement.style.fontSize = `${FONT_SIZE_DEFAULT_PCT}%`;
        localStorage.setItem('fontSizePct', fontSizePct);
        CarbonWiseUI.announce('Text size reset to default.');
    });
}

// ── Authentication Event Handlers ────────────────────────────────────────────

/**
 * Attach all authentication-related event listeners: tab switching, registration
 * form submission, login form submission, and logout click.
 *
 * @returns {void}
 */
function setupAuthListeners() {
    // Auth tab switch — show login panel
    DOM.tabLogin.addEventListener('click', () => {
        DOM.tabLogin.classList.add('active');
        DOM.tabLogin.setAttribute('aria-selected', 'true');
        DOM.tabRegister.classList.remove('active');
        DOM.tabRegister.setAttribute('aria-selected', 'false');
        DOM.panelLogin.classList.remove('hidden');
        DOM.panelRegister.classList.add('hidden');
    });

    // Auth tab switch — show registration panel
    DOM.tabRegister.addEventListener('click', () => {
        DOM.tabRegister.classList.add('active');
        DOM.tabRegister.setAttribute('aria-selected', 'true');
        DOM.tabLogin.classList.remove('active');
        DOM.tabLogin.setAttribute('aria-selected', 'false');
        DOM.panelRegister.classList.remove('hidden');
        DOM.panelLogin.classList.add('hidden');
    });

    // Registration form — validate fields and submit to server
    DOM.formRegister.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Clear any previous field-level error messages
        DOM.errRegUsername.textContent = '';
        DOM.errRegEmail.textContent = '';
        DOM.errRegPassword.textContent = '';

        const username = DOM.regUsername.value;
        const email = DOM.regEmail.value;
        const password = DOM.regPassword.value;

        try {
            await CarbonWiseAPI.register(username, email, password);
            CarbonWiseUI.announce("Registration successful. Please log in with your credentials.");
            alert("Account created! Please sign in.");
            DOM.tabLogin.click();
        } catch (err) {
            const msg = err.message || "Registration failed.";
            // Route the error message to the relevant field error label
            if (msg.toLowerCase().includes("username")) {
                DOM.errRegUsername.textContent = msg;
            } else if (msg.toLowerCase().includes("email")) {
                DOM.errRegEmail.textContent = msg;
            } else {
                DOM.errRegPassword.textContent = msg;
            }
        }
    });

    // Login form — authenticate and transition to dashboard
    DOM.formLogin.addEventListener('submit', async (e) => {
        e.preventDefault();

        DOM.errLoginEmail.textContent = '';
        DOM.errLoginPassword.textContent = '';

        const email = DOM.loginEmail.value;
        const password = DOM.loginPassword.value;

        try {
            const response = await CarbonWiseAPI.login(email, password);
            if (response && response.data) {
                handleLoginSuccess(response.data);
            }
        } catch (err) {
            const msg = err.message || "Login failed.";
            // Route the error to the password field for bad credentials,
            // and to the email field for everything else
            if (msg.toLowerCase().includes("password")) {
                DOM.errLoginPassword.textContent = msg;
            } else {
                DOM.errLoginEmail.textContent = msg;
            }
        }
    });

    // Logout — clear local state and return to auth view
    DOM.btnLogout.addEventListener('click', async () => {
        try {
            await CarbonWiseAPI.logout();
        } catch (e) {
            // Ignore network errors on logout — clear local state regardless
        }
        currentUser = null;
        latestCalculation = null;
        showAuthView();
    });
}

/**
 * Handle a successful authentication event by updating shared state and
 * loading the dashboard.
 *
 * @param {Object} user - Authenticated user profile document from the server.
 * @returns {void}
 */
function handleLoginSuccess(user) {
    currentUser = user;
    showDashboardView();
    loadDashboardData();
}

// ── Dashboard Data Loading ───────────────────────────────────────────────────

/**
 * Fetch and render the full dashboard dataset after authentication.
 *
 * Executes three sequential requests to avoid race conditions on the
 * session-dependent endpoints:
 *  1. Profile — streak count and earned badges.
 *  2. Analytics summary — scorecard statistics.
 *  3. History — most recent footprint entry plus chart data.
 *
 * When history is present, also triggers coach insights and action plan
 * loading in parallel.
 *
 * @async
 * @returns {Promise<void>}
 */
async function loadDashboardData() {
    try {
        // 1. Refresh profile for current streak count and badge list
        const profileResponse = await CarbonWiseAPI.getProfile();
        if (profileResponse && profileResponse.data) {
            currentUser = profileResponse.data;
            DOM.streakValue.textContent = currentUser.streak || 0;
            CarbonWiseUI.updateBadges(currentUser.badges, BADGE_CONFIGS);
        }

        // 2. Load telemetry scorecard statistics
        const teleResponse = await CarbonWiseAPI.getTelemetrySummary();
        if (teleResponse && teleResponse.data) {
            CarbonWiseUI.updateAnalyticsSummary(teleResponse.data);
        }

        // 3. Load history and drive subsequent chart and coach rendering
        const historyResponse = await CarbonWiseAPI.getHistory();
        const history = historyResponse.data || [];

        if (history.length > 0) {
            latestCalculation = history[0];

            // Pre-populate calculator form with the user's last submission
            populateCalculatorInputs(latestCalculation.inputs);

            CarbonWiseUI.updateScorecard(latestCalculation.eco_score, latestCalculation.category_scores);

            // Chart + prediction and coach + plan can run concurrently since
            // they do not depend on each other's results
            loadChartAndPredictions();
            loadCoachInsights();
            loadActionPlan();
        } else {
            // First-time user — show the empty-state scorecard
            CarbonWiseUI.updateScorecard(null, {});
        }
    } catch (e) {
        console.error("Failed to load dashboard dataset:", e);
    }
}

/**
 * Populate the calculator form inputs with values from a previous submission.
 *
 * Allows users to review and adjust their last reported values rather than
 * starting from zero each time they open the calculator.
 *
 * @param {Object} inputs - Previous calculator input document from the server,
 *   containing {@code transport}, {@code energy}, {@code food}, and
 *   {@code consumption} sub-objects.
 * @returns {void}
 */
function populateCalculatorInputs(inputs) {
    if (!inputs) return;

    DOM.calcGasCar.value = inputs.transport.gas_car_km || 0;
    DOM.calcElectricCar.value = inputs.transport.electric_car_km || 0;
    DOM.calcTransit.value = inputs.transport.public_transit_km || 0;
    DOM.calcFlight.value = inputs.transport.flight_km || 0;

    DOM.calcGridKwh.value = inputs.energy.grid_kwh || 0;
    DOM.calcCleanKwh.value = inputs.energy.clean_kwh || 0;

    DOM.calcDiet.value = inputs.food.diet || 'balanced';
    DOM.calcShopping.value = inputs.consumption.shopping_habit || 'average_shopper';
}

// ── Dashboard Event Listeners ────────────────────────────────────────────────

/**
 * Attach event listeners for dashboard interactions: calculator form submission,
 * coach refresh button, and action plan tab switching.
 *
 * @returns {void}
 */
function setupDashboardListeners() {
    DOM.formCalculator.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Build the payload from cached DOM references for efficiency
        const payload = {
            transport: {
                gas_car_km: parseFloat(DOM.calcGasCar.value) || 0.0,
                electric_car_km: parseFloat(DOM.calcElectricCar.value) || 0.0,
                public_transit_km: parseFloat(DOM.calcTransit.value) || 0.0,
                flight_km: parseFloat(DOM.calcFlight.value) || 0.0
            },
            energy: {
                grid_kwh: parseFloat(DOM.calcGridKwh.value) || 0.0,
                clean_kwh: parseFloat(DOM.calcCleanKwh.value) || 0.0
            },
            food: { diet: DOM.calcDiet.value },
            consumption: { shopping_habit: DOM.calcShopping.value }
        };

        try {
            const response = await CarbonWiseAPI.calculateFootprint(payload);
            if (response && response.data) {
                latestCalculation = response.data;
                CarbonWiseUI.announce("Footprint calculated successfully. Score and dashboard updating.");

                // Notify the user about any newly unlocked badges
                if (latestCalculation.newly_awarded_badges && latestCalculation.newly_awarded_badges.length > 0) {
                    const titles = latestCalculation.newly_awarded_badges.map(id => BADGE_CONFIGS[id].title).join(", ");
                    alert(`Congratulations! You unlocked new badges: ${titles}`);
                }

                // Reload the entire dashboard to reflect updated scores and telemetry
                loadDashboardData();
            }
        } catch (err) {
            alert(err.message || "Failed to save carbon calculation.");
        }
    });

    DOM.btnRefreshCoach.addEventListener('click', () => {
        loadCoachInsights();
    });

    // Plan tab switching — update the active tab and re-render the action list
    const planTabs = ["daily", "weekly", "monthly"];
    planTabs.forEach(tab => {
        document.getElementById(`tab-plan-${tab}`).addEventListener('click', (e) => {
            planTabs.forEach(t => {
                document.getElementById(`tab-plan-${t}`).classList.remove('active');
                document.getElementById(`tab-plan-${t}`).setAttribute('aria-selected', 'false');
            });
            e.target.classList.add('active');
            e.target.setAttribute('aria-selected', 'true');
            activePlanTab = tab;
            CarbonWiseUI.updateActionPlan(currentActionPlan, activePlanTab);
        });
    });
}

// ── Charts & Predictions ─────────────────────────────────────────────────────

/**
 * Fetch historical footprint records and AI predictions, then render the
 * combined dual-line chart.
 *
 * Prediction loading failures are suppressed with a warning since the chart
 * can render historical data alone without the forecast overlay.
 *
 * @async
 * @returns {Promise<void>}
 */
async function loadChartAndPredictions() {
    try {
        const historyResponse = await CarbonWiseAPI.getHistory();
        const history = historyResponse.data || [];

        let predictions = null;
        try {
            const predResponse = await CarbonWiseAPI.getPredictions();
            if (predResponse && predResponse.data) {
                predictions = predResponse.data;

                // Show the AI reasoning panel when predictions are available
                DOM.predictionPanel.classList.remove('hidden');
                DOM.predictionText.textContent = predictions.reasoning;
            }
        } catch (e) {
            console.warn("Prediction load failed — rendering chart without forecast:", e);
        }

        CarbonWiseCharts.renderHistoryAndPrediction(history, predictions);
    } catch (e) {
        console.error("Failed to render history charts:", e);
    }
}

// ── Coach & Planner ──────────────────────────────────────────────────────────

/**
 * Fetch and render personalised coaching insights, showing a loading spinner
 * during the request.
 *
 * @async
 * @returns {Promise<void>}
 */
async function loadCoachInsights() {
    // Show spinner and hide stale content during the network request
    DOM.coachLoader.classList.remove('hidden');
    DOM.coachPanel.classList.add('hidden');

    try {
        const response = await CarbonWiseAPI.getCoachInsights();
        if (response && response.data) {
            CarbonWiseUI.updateCoachPanel(response.data, handleCompleteGoal);
        }
    } catch (e) {
        console.error("Failed to fetch coach insights:", e);
    } finally {
        // Always hide spinner and reveal panel — even on error — so the UI
        // does not appear stuck in a loading state
        DOM.coachLoader.classList.add('hidden');
        DOM.coachPanel.classList.remove('hidden');
    }
}

/**
 * Fetch and store the structured action plan from the server.
 *
 * Stores the result in {@code currentActionPlan} and triggers an immediate
 * render of the active schedule tab.
 *
 * @async
 * @returns {Promise<void>}
 */
async function loadActionPlan() {
    try {
        const response = await CarbonWiseAPI.getActionPlan();
        if (response && response.data) {
            currentActionPlan = response.data;
            CarbonWiseUI.updateActionPlan(currentActionPlan, activePlanTab);
        }
    } catch (e) {
        console.error("Failed to load Action Plan:", e);
    }
}

/**
 * Record a coaching goal as completed and refresh the dashboard statistics.
 *
 * Called from the goal card "Complete" button rendered by
 * {@link CarbonWiseUI.updateCoachPanel}.
 *
 * @async
 * @param {string} goalTitle - Display title of the completed goal.
 * @param {number} carbonSaved - Estimated kg CO2e saved by completing the goal.
 * @returns {Promise<void>}
 */
async function handleCompleteGoal(goalTitle, carbonSaved) {
    try {
        const response = await CarbonWiseAPI.completeGoal(goalTitle, carbonSaved);
        if (response && response.data) {
            CarbonWiseUI.announce(`Goal completed! Saved ${carbonSaved} kg of CO2.`);

            // Reload the dashboard to reflect updated goal count and savings total
            loadDashboardData();
        }
    } catch (e) {
        console.error("Failed to log goal completion:", e);
    }
}

// ── Simulator ────────────────────────────────────────────────────────────────

/**
 * Attach input listeners to the three lifestyle simulator sliders.
 *
 * Each slider immediately updates its percentage label, then triggers a
 * debounced API call ({@code SIMULATOR_DEBOUNCE_MS} ms) to avoid flooding
 * the server during rapid drag operations.
 *
 * @returns {void}
 */
function setupSimulatorListeners() {
    // Debounced handler — waits SIMULATOR_DEBOUNCE_MS ms after the last slider
    // movement before sending the API request
    const runSimulation = debounce(async () => {
        if (!latestCalculation || !latestCalculation.inputs) {
            return;
        }

        const payload = {
            public_transit_shift: parseFloat(DOM.simTransit.value),
            meat_reduction: parseFloat(DOM.simDiet.value),
            clean_energy_shift: parseFloat(DOM.simEnergy.value),
            base_footprint: latestCalculation.inputs
        };

        try {
            const response = await CarbonWiseAPI.simulateScenario(payload);
            if (response && response.data) {
                const results = response.data;

                // Update the three result labels with the computed projection values
                DOM.simProjected.textContent = `${results.projected_emissions.total} kg`;
                DOM.simReduction.textContent = `${results.potential_reduction_kg} kg (${results.potential_reduction_pct}%)`;
                DOM.simScore.textContent = `${results.projected_score} / 100`;

                // Fetch fresh history for the chart re-render
                const historyResponse = await CarbonWiseAPI.getHistory();
                const history = historyResponse.data || [];

                // Construct a synthetic prediction that maps the simulation projection
                // onto the chart's forecast line without requiring a separate AI call
                const simulatedPredictions = {
                    projection_30_days: results.projected_emissions.total,
                    projection_90_days: results.projected_emissions.total,
                    reasoning: `Simulated path projections: Shifting habits lowers carbon output to ${results.projected_emissions.total} kg.`
                };

                CarbonWiseCharts.renderHistoryAndPrediction(history, simulatedPredictions);
                CarbonWiseUI.announce(`Simulation recalculated: potential reduction of ${results.potential_reduction_kg} kilograms.`);
            }
        } catch (e) {
            console.error("Simulation request failed:", e);
        }
    }, SIMULATOR_DEBOUNCE_MS);

    // Each slider instantly updates its label text, then triggers the debounced API call
    DOM.simTransit.addEventListener('input', (e) => {
        DOM.simTransitLbl.textContent = `${e.target.value}%`;
        runSimulation();
    });

    DOM.simDiet.addEventListener('input', (e) => {
        DOM.simDietLbl.textContent = `${e.target.value}%`;
        runSimulation();
    });

    DOM.simEnergy.addEventListener('input', (e) => {
        DOM.simEnergyLbl.textContent = `${e.target.value}%`;
        runSimulation();
    });
}
