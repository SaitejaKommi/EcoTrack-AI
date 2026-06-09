/**
 * @fileoverview CarbonWise UI Views Renderer.
 *
 * Manages all DOM mutation operations: updating the eco scorecard, rendering
 * badge cards, populating the coach insights and goal panels, building the
 * action plan list, refreshing dashboard statistics, and firing ARIA live-region
 * announcements for screen reader compatibility.
 *
 * All rendering methods are static so callers do not need to manage an instance.
 * DOM references are cached via {@link CarbonWiseUI.initDOM} and reused throughout
 * the page lifecycle to avoid repeated document queries.
 *
 * Design principle: Pure view layer — no network calls, no business logic.
 * All data must be passed in as arguments from the app controller.
 */

/** Screen-reader announcement delay in ms (see A11Y_ANNOUNCE_DELAY_MS constant). */
const A11Y_ANNOUNCE_DELAY_MS = 100;

/** Eco score threshold above which the "outstanding" description is shown. */
const ECO_SCORE_HIGH_THRESHOLD = 80;

/** Eco score threshold above which the "good" description is shown. */
const ECO_SCORE_AVERAGE_THRESHOLD = 50;

/** Impact tier labels used to estimate carbon savings from goal completion. */
const IMPACT_HIGH = 'High';
const IMPACT_MEDIUM = 'Medium';

class CarbonWiseUI {
    /**
     * Cached DOM references populated during {@link CarbonWiseUI.initDOM}.
     * @type {Object.<string, HTMLElement|null>}
     */
    static DOM = {
        announcer: null,
        scoreLabel: null,
        scoreDesc: null,
        badgesGrid: null,
        insightsList: null,
        goalsGrid: null,
        actionPlanList: null,
        statCalcs: null,
        statSims: null,
        statGoals: null,
        statSavings: null
    };

    /**
     * Populate the UI DOM cache from the live document.
     *
     * Must be called once after {@code DOMContentLoaded} fires, before any
     * other methods are invoked. Subsequent method calls fall back to inline
     * {@code getElementById} lookups for safety if this was not called.
     *
     * @returns {void}
     */
    static initDOM() {
        this.DOM.announcer = document.getElementById('a11y-announcer');
        this.DOM.scoreLabel = document.getElementById('lbl-dashboard-score');
        this.DOM.scoreDesc = document.getElementById('lbl-score-explanation');
        this.DOM.badgesGrid = document.getElementById('lst-earned-badges');
        this.DOM.insightsList = document.getElementById('lst-coach-insights');
        this.DOM.goalsGrid = document.getElementById('lst-weekly-goals');
        this.DOM.actionPlanList = document.getElementById('lst-action-plan');
        this.DOM.statCalcs = document.getElementById('lbl-stat-calcs');
        this.DOM.statSims = document.getElementById('lbl-stat-sims');
        this.DOM.statGoals = document.getElementById('lbl-stat-goals');
        this.DOM.statSavings = document.getElementById('lbl-stat-savings');
    }

    /**
     * Fire an ARIA live-region announcement for screen reader users.
     *
     * Clears the announcer element first, then re-populates it after a brief
     * delay ({@code A11Y_ANNOUNCE_DELAY_MS} ms). The DOM mutation followed by
     * the timeout ensures that assistive technologies catch the layout change
     * as a new announcement rather than ignoring a repeated identical value.
     *
     * @param {string} message - Plain text message to announce.
     * @returns {void}
     */
    static announce(message) {
        const announcer = this.DOM.announcer || document.getElementById('a11y-announcer');
        if (announcer) {
            announcer.textContent = '';
            // Delay ensures the AT notices the DOM transition before the new content arrives
            setTimeout(() => {
                announcer.textContent = message;
            }, A11Y_ANNOUNCE_DELAY_MS);
        }
    }

    /**
     * Render the overall Eco Score and per-category progress bars.
     *
     * Displays a descriptive tier message based on the score relative to the
     * {@code ECO_SCORE_HIGH_THRESHOLD} and {@code ECO_SCORE_AVERAGE_THRESHOLD}
     * boundaries. When {@code score} is {@code null}, renders the empty state
     * prompting the user to run the calculator.
     *
     * @param {number|null} score - Overall eco score (0–100), or {@code null}
     *   when no calculation exists yet.
     * @param {Object.<string, number>} categoryScores - Per-category scores keyed by
     *   category name: {@code "transport"}, {@code "energy"}, {@code "food"},
     *   {@code "consumption"}.
     * @returns {void}
     */
    static updateScorecard(score, categoryScores) {
        const scoreLbl = this.DOM.scoreLabel || document.getElementById('lbl-dashboard-score');
        const descLbl = this.DOM.scoreDesc || document.getElementById('lbl-score-explanation');

        if (!scoreLbl) return;

        scoreLbl.textContent = score !== null ? score : '--';

        if (score === null) {
            descLbl.textContent = "Log your carbon footprint parameters above to compute your Eco Score.";
            return;
        }

        // Select the description tier based on score thresholds
        let review = "";
        if (score >= ECO_SCORE_HIGH_THRESHOLD) {
            review = "Outstanding! Your footprint is extremely low, demonstrating highly sustainable lifestyle habits.";
        } else if (score >= ECO_SCORE_AVERAGE_THRESHOLD) {
            review = "Good work. You are performing better than the average carbon footprint baseline. Check goals to improve further.";
        } else {
            review = "Your footprint exceeds average baselines. Explore the Simulator and AI suggestions to start saving carbon.";
        }

        descLbl.textContent = review;
        this.announce(`Your Eco Score has been updated to ${score}. ${review}`);

        // Update each category progress bar width and percentage label
        const categories = ["transport", "energy", "food", "consumption"];
        categories.forEach(cat => {
            const catScore = categoryScores[cat] !== undefined ? categoryScores[cat] : 0;
            const barFill = document.getElementById(`bar-fill-${cat}`);
            const scoreVal = document.getElementById(`lbl-cat-score-${cat}`);

            if (barFill && scoreVal) {
                barFill.style.width = `${catScore}%`;
                scoreVal.textContent = `${Math.round(catScore)}%`;
            }
        });
    }

    /**
     * Render the badge grid, showing locked and unlocked states for all badges.
     *
     * Iterates all badge configurations and marks each card as unlocked when
     * the badge ID appears in {@code unlockedBadgesList}. Unlocked cards
     * receive the {@code "unlocked"} CSS class for visual differentiation.
     *
     * @param {Array<{badge_id: string}>} unlockedBadgesList - Array of earned
     *   badge sub-documents from the user profile.
     * @param {Object.<string, {title: string, description: string, icon: string}>} badgeConfigs -
     *   Full badge configuration map from the app controller.
     * @returns {void}
     */
    static updateBadges(unlockedBadgesList, badgeConfigs) {
        const grid = this.DOM.badgesGrid || document.getElementById('lst-earned-badges');
        if (!grid) return;

        grid.innerHTML = '';

        // Build a Set for O(1) membership tests during badge card iteration
        const unlockedIds = new Set((unlockedBadgesList || []).map(b => b.badge_id));

        Object.keys(badgeConfigs).forEach(badgeId => {
            const cfg = badgeConfigs[badgeId];
            const isUnlocked = unlockedIds.has(badgeId);

            const card = document.createElement('div');
            card.className = `badge-card ${isUnlocked ? 'unlocked' : ''}`;
            card.setAttribute('tabindex', '0');
            card.setAttribute('role', 'listitem');
            card.setAttribute('aria-label', `${cfg.title} badge. ${isUnlocked ? 'Unlocked' : 'Locked'}. ${cfg.description}`);

            card.innerHTML = `
                <div class="badge-icon-box">
                    <i class="bi bi-${cfg.icon}"></i>
                </div>
                <span class="badge-name">${cfg.title}</span>
            `;

            grid.appendChild(card);
        });
    }

    /**
     * Render the coach insights list and weekly goal cards.
     *
     * Populates the insights panel with bullet-point observations and
     * explainable suggestion cards, then renders the interactive goal cards
     * with "Complete" buttons that call {@code completeGoalCallback}.
     *
     * @param {Object} insightsData - Coaching data from the server containing:
     *   {@code insights} (string[]), {@code suggestions} (Object[]),
     *   {@code weekly_goals} (Object[]).
     * @param {Function} completeGoalCallback - Async function {@code (title: string, carbonSaved: number) => Promise<void>}
     *   called when a goal's Complete button is clicked.
     * @returns {void}
     */
    static updateCoachPanel(insightsData, completeGoalCallback) {
        const insightsList = this.DOM.insightsList || document.getElementById('lst-coach-insights');
        const goalsGrid = this.DOM.goalsGrid || document.getElementById('lst-weekly-goals');

        if (!insightsList || !goalsGrid) return;

        insightsList.innerHTML = '';
        goalsGrid.innerHTML = '';

        const insights = insightsData.insights || [];
        const suggestions = insightsData.suggestions || [];
        const weeklyGoals = insightsData.weekly_goals || [];

        // Render plain-text insight bullet points
        if (insights.length === 0) {
            insightsList.innerHTML = `<li>No recommendations logged yet. Calculate your footprint above.</li>`;
        } else {
            insights.forEach(ins => {
                const li = document.createElement('li');
                li.textContent = ins;
                insightsList.appendChild(li);
            });
        }

        // Render explainable suggestion cards with impact and outcome details
        if (suggestions.length > 0) {
            suggestions.forEach(sug => {
                const li = document.createElement('li');
                li.className = 'suggestion-item-explain';
                li.innerHTML = `
                    <div class="sug-main">
                        <strong>Recommendation:</strong> ${sug.text}
                    </div>
                    <div class="sug-details-box">
                        <p class="sug-why"><strong>Why Chosen:</strong> ${sug.why_chosen}</p>
                        <div class="sug-metrics-row">
                            <span class="sug-metric"><i class="bi bi-shield-fill-plus text-green"></i> Est. Savings: ${sug.estimated_impact}</span>
                            <span class="sug-metric"><i class="bi bi-activity text-cyan"></i> Outcome: ${sug.expected_outcome}</span>
                        </div>
                    </div>
                `;
                insightsList.appendChild(li);
            });
        }

        // Render interactive goal cards with a complete button
        if (weeklyGoals.length === 0) {
            goalsGrid.innerHTML = `<p class="auth-subtitle">No weekly goals available.</p>`;
        } else {
            weeklyGoals.forEach((goal, index) => {
                const card = document.createElement('article');
                card.className = 'goal-card';
                card.setAttribute('aria-labelledby', `goal-title-${index}`);

                // Map the impact tier label to a carbon savings estimate constant
                const carbonSavedEstimate =
                    goal.impact === IMPACT_HIGH ? GOAL_CARBON_HIGH_IMPACT
                    : goal.impact === IMPACT_MEDIUM ? GOAL_CARBON_MEDIUM_IMPACT
                    : GOAL_CARBON_LOW_IMPACT;

                card.innerHTML = `
                    <div class="goal-left">
                        <span class="goal-title" id="goal-title-${index}">${goal.title}</span>
                        <p class="goal-desc">${goal.description}</p>
                        <span class="badge-impact impact-${goal.impact.toLowerCase()}">${goal.impact} Impact (+${goal.points} pts)</span>
                    </div>
                    <button class="btn-complete" data-title="${goal.title}" data-saved="${carbonSavedEstimate}" aria-label="Mark ${goal.title} as completed">
                        Complete
                    </button>
                `;

                const btn = card.querySelector('.btn-complete');
                btn.addEventListener('click', async (e) => {
                    const title = e.target.getAttribute('data-title');
                    const saved = parseFloat(e.target.getAttribute('data-saved'));
                    // Disable button immediately to prevent duplicate submissions
                    e.target.disabled = true;
                    e.target.textContent = "Logged ✓";
                    await completeGoalCallback(title, saved);
                });

                goalsGrid.appendChild(card);
            });
        }
    }

    /**
     * Render the action plan list for the currently selected schedule tab.
     *
     * Displays prioritised actions for the {@code activeSchedule} key
     * ({@code "daily"}, {@code "weekly"}, or {@code "monthly"}). Each action
     * card shows the task, category, impact level, cost indicator, and difficulty.
     *
     * @param {Object.<string, Array<Object>>} planData - Full action plan object
     *   with {@code daily}, {@code weekly}, and {@code monthly} action arrays.
     * @param {string} activeSchedule - Currently selected tab key.
     * @returns {void}
     */
    static updateActionPlan(planData, activeSchedule) {
        const list = this.DOM.actionPlanList || document.getElementById('lst-action-plan');
        if (!list) return;

        list.innerHTML = '';
        const scheduleActions = planData[activeSchedule] || [];

        if (scheduleActions.length === 0) {
            list.innerHTML = `<li>Log calculator data to build a prioritized action plan.</li>`;
            return;
        }

        scheduleActions.forEach(action => {
            const li = document.createElement('li');
            li.className = 'action-item';

            // Map cost string to a concise price-indicator icon for compact display
            const costIcon =
                action.cost === 'Free' ? '0'
                : action.cost === 'Low' ? '$'
                : action.cost === 'Moderate' ? '$$'
                : '$$$';

            li.innerHTML = `
                <div class="action-details">
                    <span class="action-title">${action.task}</span>
                    <div class="action-meta">
                        <span><i class="bi bi-tag-fill"></i> ${action.category.toUpperCase()}</span>
                        <span><i class="bi bi-bar-chart-fill"></i> ${action.impact} Impact</span>
                        <span><i class="bi bi-cash"></i> Cost: ${action.cost}</span>
                        <span><i class="bi bi-gear-fill"></i> ${action.difficulty}</span>
                    </div>
                </div>
            `;
            list.appendChild(li);
        });
    }

    /**
     * Update the dashboard scorecard statistics with fresh telemetry totals.
     *
     * @param {Object} summaryData - Aggregated analytics summary from the server
     *   containing {@code calculations_run}, {@code simulations_run},
     *   {@code goals_completed}, and {@code estimated_carbon_saved_kg}.
     * @returns {void}
     */
    static updateAnalyticsSummary(summaryData) {
        const calcs = this.DOM.statCalcs || document.getElementById('lbl-stat-calcs');
        const sims = this.DOM.statSims || document.getElementById('lbl-stat-sims');
        const goals = this.DOM.statGoals || document.getElementById('lbl-stat-goals');
        const savings = this.DOM.statSavings || document.getElementById('lbl-stat-savings');

        if (calcs) calcs.textContent = summaryData.calculations_run || 0;
        if (sims) sims.textContent = summaryData.simulations_run || 0;
        if (goals) goals.textContent = summaryData.goals_completed || 0;
        if (savings) savings.textContent = `${summaryData.estimated_carbon_saved_kg || 0} kg`;
    }
}
