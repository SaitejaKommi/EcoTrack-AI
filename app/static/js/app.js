/**
 * CarbonWise Main Application Controller
 * Handles view routers, form submits, interactive sliders, and accessibility setups.
 */

// Shared client state
let currentUser = null;
let latestCalculation = null;
let currentActionPlan = {};
let activePlanTab = 'daily';

// Badges config duplicate for UI rendering lookup matching backend constants
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

// Centralized DOM caching namespace to eliminate duplicate queries
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
    
    // Inputs
    calcGasCar: null,
    calcElectricCar: null,
    calcTransit: null,
    calcFlight: null,
    calcGridKwh: null,
    calcCleanKwh: null,
    calcDiet: null,
    calcShopping: null,
    
    // Simulator
    simTransit: null,
    simDiet: null,
    simEnergy: null,
    simTransitLbl: null,
    simDietLbl: null,
    simEnergyLbl: null,
    simProjected: null,
    simReduction: null,
    simScore: null,
    
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

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

/**
 * Bootstraps the application state and event handlers.
 */
async function initApp() {
    DOM.init();
    CarbonWiseUI.initDOM();
    setupAccessibilityControls();
    setupAuthListeners();
    setupDashboardListeners();
    setupSimulatorListeners();
    
    // Check if user is already authenticated
    try {
        const response = await CarbonWiseAPI.getProfile();
        if (response && response.data) {
            handleLoginSuccess(response.data);
        } else {
            showAuthView();
        }
    } catch (e) {
        showAuthView();
    }
}

// --- VIEW CONTROLLERS ---
function showAuthView() {
    DOM.viewAuth.classList.remove('hidden');
    DOM.viewDashboard.classList.add('hidden');
    DOM.userGreeting.textContent = 'Welcome, Guest';
}

function showDashboardView() {
    DOM.viewAuth.classList.add('hidden');
    DOM.viewDashboard.classList.remove('hidden');
    if (currentUser) {
        DOM.userGreeting.textContent = `Welcome, ${currentUser.username}`;
    }
}

// --- ACCESSIBILITY CONFIGURATION ---
function setupAccessibilityControls() {
    // Load user preferences from local storage
    if (localStorage.getItem('contrast') === 'enabled') {
        document.body.classList.add('high-contrast');
        DOM.contrastBtn.setAttribute('aria-pressed', 'true');
    }
    
    if (localStorage.getItem('motion') === 'reduced') {
        document.body.classList.add('reduced-motion');
        DOM.motionBtn.setAttribute('aria-pressed', 'true');
    }

    let fontSizePct = parseInt(localStorage.getItem('fontSizePct')) || 100;
    document.documentElement.style.fontSize = `${fontSizePct}%`;

    // Contrast Toggle
    DOM.contrastBtn.addEventListener('click', () => {
        const active = document.body.classList.toggle('high-contrast');
        DOM.contrastBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
        localStorage.setItem('contrast', active ? 'enabled' : 'disabled');
        CarbonWiseUI.announce(`High contrast mode ${active ? 'enabled' : 'disabled'}.`);
        
        // Re-render chart to update theme grid colors
        if (latestCalculation) {
            loadChartAndPredictions();
        }
    });

    // Motion Toggle
    DOM.motionBtn.addEventListener('click', () => {
        const active = document.body.classList.toggle('reduced-motion');
        DOM.motionBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
        localStorage.setItem('motion', active ? 'reduced' : 'normal');
        CarbonWiseUI.announce(`Reduced motion mode ${active ? 'enabled' : 'disabled'}.`);
    });

    // Font Sizing
    DOM.fontInc.addEventListener('click', () => {
        if (fontSizePct < 140) {
            fontSizePct += 10;
            document.documentElement.style.fontSize = `${fontSizePct}%`;
            localStorage.setItem('fontSizePct', fontSizePct);
            CarbonWiseUI.announce(`Text size increased to ${fontSizePct} percent.`);
        }
    });

    DOM.fontDec.addEventListener('click', () => {
        if (fontSizePct > 80) {
            fontSizePct -= 10;
            document.documentElement.style.fontSize = `${fontSizePct}%`;
            localStorage.setItem('fontSizePct', fontSizePct);
            CarbonWiseUI.announce(`Text size decreased to ${fontSizePct} percent.`);
        }
    });

    DOM.fontReset.addEventListener('click', () => {
        fontSizePct = 100;
        document.documentElement.style.fontSize = '100%';
        localStorage.setItem('fontSizePct', fontSizePct);
        CarbonWiseUI.announce(`Text size reset to default.`);
    });
}

// --- EVENT HANDLERS ---
function setupAuthListeners() {
    // Auth Tab switching
    DOM.tabLogin.addEventListener('click', () => {
        DOM.tabLogin.classList.add('active');
        DOM.tabLogin.setAttribute('aria-selected', 'true');
        DOM.tabRegister.classList.remove('active');
        DOM.tabRegister.setAttribute('aria-selected', 'false');
        DOM.panelLogin.classList.remove('hidden');
        DOM.panelRegister.classList.add('hidden');
    });

    DOM.tabRegister.addEventListener('click', () => {
        DOM.tabRegister.classList.add('active');
        DOM.tabRegister.setAttribute('aria-selected', 'true');
        DOM.tabLogin.classList.remove('active');
        DOM.tabLogin.setAttribute('aria-selected', 'false');
        DOM.panelRegister.classList.remove('hidden');
        DOM.panelLogin.classList.add('hidden');
    });

    // Form Sign Up submit
    DOM.formRegister.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset warnings
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
            if (msg.toLowerCase().includes("username")) {
                DOM.errRegUsername.textContent = msg;
            } else if (msg.toLowerCase().includes("email")) {
                DOM.errRegEmail.textContent = msg;
            } else {
                DOM.errRegPassword.textContent = msg;
            }
        }
    });

    // Form Login submit
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
            if (msg.toLowerCase().includes("password")) {
                DOM.errLoginPassword.textContent = msg;
            } else {
                DOM.errLoginEmail.textContent = msg;
            }
        }
    });

    // Logout click
    DOM.btnLogout.addEventListener('click', async () => {
        try {
            await CarbonWiseAPI.logout();
        } catch (e) {}
        currentUser = null;
        latestCalculation = null;
        showAuthView();
    });
}

function handleLoginSuccess(user) {
    currentUser = user;
    showDashboardView();
    loadDashboardData();
}

/**
 * Loads entire dashboard dataset asynchronously.
 */
async function loadDashboardData() {
    try {
        // 1. Get user profile details for current streak / badges
        const profileResponse = await CarbonWiseAPI.getProfile();
        if (profileResponse && profileResponse.data) {
            currentUser = profileResponse.data;
            DOM.streakValue.textContent = currentUser.streak || 0;
            CarbonWiseUI.updateBadges(currentUser.badges, BADGE_CONFIGS);
        }

        // 2. Get telemetry metrics
        const teleResponse = await CarbonWiseAPI.getTelemetrySummary();
        if (teleResponse && teleResponse.data) {
            CarbonWiseUI.updateAnalyticsSummary(teleResponse.data);
        }

        // 3. Get footprint history
        const historyResponse = await CarbonWiseAPI.getHistory();
        const history = historyResponse.data || [];
        
        if (history.length > 0) {
            latestCalculation = history[0];
            
            // Populate form controls with latest inputs
            populateCalculatorInputs(latestCalculation.inputs);
            
            // Update scores
            CarbonWiseUI.updateScorecard(latestCalculation.eco_score, latestCalculation.category_scores);
            
            // Load charts & forecast lines
            loadChartAndPredictions();

            // Load coach recommendations & plans
            loadCoachInsights();
            loadActionPlan();
        } else {
            // Empty state scorecard
            CarbonWiseUI.updateScorecard(null, {});
        }
    } catch (e) {
        console.error("Failed to load dashboard dataset:", e);
    }
}

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

function setupDashboardListeners() {
    // Calculator Submit handler
    DOM.formCalculator.addEventListener('submit', async (e) => {
        e.preventDefault();
        
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
            food: {
                diet: DOM.calcDiet.value
            },
            consumption: {
                shopping_habit: DOM.calcShopping.value
            }
        };

        try {
            const response = await CarbonWiseAPI.calculateFootprint(payload);
            if (response && response.data) {
                latestCalculation = response.data;
                CarbonWiseUI.announce("Footprint calculated successfully. Score and dashboard updating.");
                
                // Show badge alert modal if new achievements unlocked
                if (latestCalculation.newly_awarded_badges && latestCalculation.newly_awarded_badges.length > 0) {
                    const titles = latestCalculation.newly_awarded_badges.map(id => BADGE_CONFIGS[id].title).join(", ");
                    alert(`Congratulations! You unlocked new badges: ${titles}`);
                }
                
                // Refresh dashboards
                loadDashboardData();
            }
        } catch (err) {
            alert(err.message || "Failed to save carbon calculation.");
        }
    });

    // Refresh Coach Insights
    DOM.btnRefreshCoach.addEventListener('click', () => {
        loadCoachInsights();
    });

    // Planner tab listeners
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

// --- CHARTS & PREDICTIONS INTERACTION ---
async function loadChartAndPredictions() {
    try {
        const historyResponse = await CarbonWiseAPI.getHistory();
        const history = historyResponse.data || [];
        
        let predictions = null;
        try {
            const predResponse = await CarbonWiseAPI.getPredictions();
            if (predResponse && predResponse.data) {
                predictions = predResponse.data;
                
                // Show prediction details box
                DOM.predictionPanel.classList.remove('hidden');
                DOM.predictionText.textContent = predictions.reasoning;
            }
        } catch (e) {
            console.warn("Prediction load failed:", e);
        }

        // Render dual lines chart
        CarbonWiseCharts.renderHistoryAndPrediction(history, predictions);
    } catch (e) {
        console.error("Failed to render history charts:", e);
    }
}

// --- COACH & PLANNER LOGICS ---
async function loadCoachInsights() {
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
        DOM.coachLoader.classList.add('hidden');
        DOM.coachPanel.classList.remove('hidden');
    }
}

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

async function handleCompleteGoal(goalTitle, carbonSaved) {
    try {
        const response = await CarbonWiseAPI.completeGoal(goalTitle, carbonSaved);
        if (response && response.data) {
            CarbonWiseUI.announce(`Goal completed! Saved ${carbonSaved} kg of CO2.`);
            
            // Reload analytics and statistics
            loadDashboardData();
        }
    } catch (e) {
        console.error("Failed to log goal completion:", e);
    }
}

// --- INTERACTIVE SIMULATOR MANAGER ---
function setupSimulatorListeners() {
    // Debounced simulator execution
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
                
                // Update slider outputs UI
                DOM.simProjected.textContent = `${results.projected_emissions.total} kg`;
                DOM.simReduction.textContent = `${results.potential_reduction_kg} kg (${results.potential_reduction_pct}%)`;
                DOM.simScore.textContent = `${results.projected_score} / 100`;
                
                // Rerender Chart.js line with custom simulation projections overlay!
                const historyResponse = await CarbonWiseAPI.getHistory();
                const history = historyResponse.data || [];
                
                // Construct a mock prediction mapping the simulation project
                const simulatedPredictions = {
                    projection_30_days: results.projected_emissions.total,
                    projection_90_days: results.projected_emissions.total,
                    reasoning: `Simulated path projections: Shifting habits lowers carbon output to ${results.projected_emissions.total} kg.`
                };
                
                // Re-render chart incorporating simulation results
                CarbonWiseCharts.renderHistoryAndPrediction(history, simulatedPredictions);
                
                CarbonWiseUI.announce(`Simulation recalculated: potential reduction of ${results.potential_reduction_kg} kilograms.`);
            }
        } catch (e) {
            console.error("Simulation request failed:", e);
        }
    }, 250); // 250ms debounce threshold to save bandwidth and API limits

    // Handle instant UI text changes and trigger debounced API calls
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
