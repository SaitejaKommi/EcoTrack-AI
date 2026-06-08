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

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

/**
 * Bootstraps the application state and event handlers.
 */
async function initApp() {
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
    document.getElementById('view-auth').classList.remove('hidden');
    document.getElementById('view-dashboard').classList.add('hidden');
    document.getElementById('user-greeting').textContent = 'Welcome, Guest';
}

function showDashboardView() {
    document.getElementById('view-auth').classList.add('hidden');
    document.getElementById('view-dashboard').classList.remove('hidden');
    if (currentUser) {
        document.getElementById('user-greeting').textContent = `Welcome, ${currentUser.username}`;
    }
}

// --- ACCESSIBILITY CONFIGURATION ---
function setupAccessibilityControls() {
    const contrastBtn = document.getElementById('btn-toggle-contrast');
    const motionBtn = document.getElementById('btn-toggle-motion');
    const fontInc = document.getElementById('btn-font-inc');
    const fontDec = document.getElementById('btn-font-dec');
    const fontReset = document.getElementById('btn-font-reset');

    // Load user preferences from local storage
    if (localStorage.getItem('contrast') === 'enabled') {
        document.body.classList.add('high-contrast');
        contrastBtn.setAttribute('aria-pressed', 'true');
    }
    
    if (localStorage.getItem('motion') === 'reduced') {
        document.body.classList.add('reduced-motion');
        motionBtn.setAttribute('aria-pressed', 'true');
    }

    let fontSizePct = parseInt(localStorage.getItem('fontSizePct')) || 100;
    document.documentElement.style.fontSize = `${fontSizePct}%`;

    // Contrast Toggle
    contrastBtn.addEventListener('click', () => {
        const active = document.body.classList.toggle('high-contrast');
        contrastBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
        localStorage.setItem('contrast', active ? 'enabled' : 'disabled');
        CarbonWiseUI.announce(`High contrast mode ${active ? 'enabled' : 'disabled'}.`);
        
        // Re-render chart to update theme grid colors
        if (latestCalculation) {
            loadChartAndPredictions();
        }
    });

    // Motion Toggle
    motionBtn.addEventListener('click', () => {
        const active = document.body.classList.toggle('reduced-motion');
        motionBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
        localStorage.setItem('motion', active ? 'reduced' : 'normal');
        CarbonWiseUI.announce(`Reduced motion mode ${active ? 'enabled' : 'disabled'}.`);
    });

    // Font Sizing
    fontInc.addEventListener('click', () => {
        if (fontSizePct < 140) {
            fontSizePct += 10;
            document.documentElement.style.fontSize = `${fontSizePct}%`;
            localStorage.setItem('fontSizePct', fontSizePct);
            CarbonWiseUI.announce(`Text size increased to ${fontSizePct} percent.`);
        }
    });

    fontDec.addEventListener('click', () => {
        if (fontSizePct > 80) {
            fontSizePct -= 10;
            document.documentElement.style.fontSize = `${fontSizePct}%`;
            localStorage.setItem('fontSizePct', fontSizePct);
            CarbonWiseUI.announce(`Text size decreased to ${fontSizePct} percent.`);
        }
    });

    fontReset.addEventListener('click', () => {
        fontSizePct = 100;
        document.documentElement.style.fontSize = '100%';
        localStorage.setItem('fontSizePct', fontSizePct);
        CarbonWiseUI.announce(`Text size reset to default.`);
    });
}

// --- EVENT HANDLERS ---
function setupAuthListeners() {
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');
    const panelLogin = document.getElementById('panel-login');
    const panelRegister = document.getElementById('panel-register');
    
    // Auth Tab switching
    tabLogin.addEventListener('click', () => {
        tabLogin.classList.add('active');
        tabLogin.setAttribute('aria-selected', 'true');
        tabRegister.classList.remove('active');
        tabRegister.setAttribute('aria-selected', 'false');
        panelLogin.classList.remove('hidden');
        panelRegister.classList.add('hidden');
    });

    tabRegister.addEventListener('click', () => {
        tabRegister.classList.add('active');
        tabRegister.setAttribute('aria-selected', 'true');
        tabLogin.classList.remove('active');
        tabLogin.setAttribute('aria-selected', 'false');
        panelRegister.classList.remove('hidden');
        panelLogin.classList.add('hidden');
    });

    // Form Sign Up submit
    document.getElementById('form-register').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset warnings
        document.getElementById('err-reg-username').textContent = '';
        document.getElementById('err-reg-email').textContent = '';
        document.getElementById('err-reg-password').textContent = '';
        
        const username = document.getElementById('reg-username').value;
        const email = document.getElementById('reg-email').value;
        const password = document.getElementById('reg-password').value;
        
        try {
            await CarbonWiseAPI.register(username, email, password);
            CarbonWiseUI.announce("Registration successful. Please log in with your credentials.");
            alert("Account created! Please sign in.");
            tabLogin.click();
        } catch (err) {
            const msg = err.message || "Registration failed.";
            if (msg.toLowerCase().includes("username")) {
                document.getElementById('err-reg-username').textContent = msg;
            } else if (msg.toLowerCase().includes("email")) {
                document.getElementById('err-reg-email').textContent = msg;
            } else {
                document.getElementById('err-reg-password').textContent = msg;
            }
        }
    });

    // Form Login submit
    document.getElementById('form-login').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        document.getElementById('err-login-email').textContent = '';
        document.getElementById('err-login-password').textContent = '';
        
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        
        try {
            const response = await CarbonWiseAPI.login(email, password);
            if (response && response.data) {
                handleLoginSuccess(response.data);
            }
        } catch (err) {
            const msg = err.message || "Login failed.";
            if (msg.toLowerCase().includes("password")) {
                document.getElementById('err-login-password').textContent = msg;
            } else {
                document.getElementById('err-login-email').textContent = msg;
            }
        }
    });

    // Logout click
    document.getElementById('btn-logout').addEventListener('click', async () => {
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
            document.getElementById('lbl-streak-value').textContent = currentUser.streak || 0;
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
    
    document.getElementById('calc-gas-car').value = inputs.transport.gas_car_km || 0;
    document.getElementById('calc-electric-car').value = inputs.transport.electric_car_km || 0;
    document.getElementById('calc-transit').value = inputs.transport.public_transit_km || 0;
    document.getElementById('calc-flight').value = inputs.transport.flight_km || 0;
    
    document.getElementById('calc-grid-kwh').value = inputs.energy.grid_kwh || 0;
    document.getElementById('calc-clean-kwh').value = inputs.energy.clean_kwh || 0;
    
    document.getElementById('calc-diet').value = inputs.food.diet || 'balanced';
    document.getElementById('calc-shopping').value = inputs.consumption.shopping_habit || 'average_shopper';
}

function setupDashboardListeners() {
    // Calculator Submit handler
    document.getElementById('form-calculator').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const payload = {
            transport: {
                gas_car_km: parseFloat(document.getElementById('calc-gas-car').value) || 0.0,
                electric_car_km: parseFloat(document.getElementById('calc-electric-car').value) || 0.0,
                public_transit_km: parseFloat(document.getElementById('calc-transit').value) || 0.0,
                flight_km: parseFloat(document.getElementById('calc-flight').value) || 0.0
            },
            energy: {
                grid_kwh: parseFloat(document.getElementById('calc-grid-kwh').value) || 0.0,
                clean_kwh: parseFloat(document.getElementById('calc-clean-kwh').value) || 0.0
            },
            food: {
                diet: document.getElementById('calc-diet').value
            },
            consumption: {
                shopping_habit: document.getElementById('calc-shopping').value
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
    document.getElementById('btn-refresh-coach').addEventListener('click', () => {
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
                const panel = document.getElementById('prediction-panel');
                panel.classList.remove('hidden');
                document.getElementById('lbl-prediction-text').textContent = predictions.reasoning;
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
    const loader = document.getElementById('coach-insights-loading');
    const panel = document.getElementById('coach-content-panel');
    
    loader.classList.remove('hidden');
    panel.classList.add('hidden');
    
    try {
        const response = await CarbonWiseAPI.getCoachInsights();
        if (response && response.data) {
            CarbonWiseUI.updateCoachPanel(response.data, handleCompleteGoal);
        }
    } catch (e) {
        console.error("Failed to fetch coach insights:", e);
    } finally {
        loader.classList.add('hidden');
        panel.classList.remove('hidden');
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
    const transitSlider = document.getElementById('sim-transit');
    const dietSlider = document.getElementById('sim-diet');
    const energySlider = document.getElementById('sim-energy');
    
    const transitLbl = document.getElementById('lbl-sim-transit');
    const dietLbl = document.getElementById('lbl-sim-diet');
    const energyLbl = document.getElementById('lbl-sim-energy');

    // Debounced simulator execution
    const runSimulation = debounce(async () => {
        if (!latestCalculation || !latestCalculation.inputs) {
            return;
        }

        const payload = {
            public_transit_shift: parseFloat(transitSlider.value),
            meat_reduction: parseFloat(dietSlider.value),
            clean_energy_shift: parseFloat(energySlider.value),
            base_footprint: latestCalculation.inputs
        };

        try {
            const response = await CarbonWiseAPI.simulateScenario(payload);
            if (response && response.data) {
                const results = response.data;
                
                // Update slider outputs UI
                document.getElementById('lbl-sim-projected').textContent = `${results.projected_emissions.total} kg`;
                document.getElementById('lbl-sim-reduction').textContent = `${results.potential_reduction_kg} kg (${results.potential_reduction_pct}%)`;
                document.getElementById('lbl-sim-score').textContent = `${results.projected_score} / 100`;
                
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
    transitSlider.addEventListener('input', (e) => {
        transitLbl.textContent = `${e.target.value}%`;
        runSimulation();
    });

    dietSlider.addEventListener('input', (e) => {
        dietLbl.textContent = `${e.target.value}%`;
        runSimulation();
    });

    energySlider.addEventListener('input', (e) => {
        energyLbl.textContent = `${e.target.value}%`;
        runSimulation();
    });
}
