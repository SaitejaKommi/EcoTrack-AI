/**
 * CarbonWise UI Views Renderer
 * Manages DOM updates, template construction, action planners, and screen reader announcements.
 */

class CarbonWiseUI {
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
     * Announces a message to screen readers using the ARIA live region.
     */
    static announce(message) {
        const announcer = this.DOM.announcer || document.getElementById('a11y-announcer');
        if (announcer) {
            announcer.textContent = '';
            // Timeout ensures screen readers catch the layout adjustment
            setTimeout(() => {
                announcer.textContent = message;
            }, 100);
        }
    }

    /**
     * Renders the user's overall Eco Scorecard.
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

        // Set analytical summary description based on score tiers
        let review = "";
        if (score >= 80) {
            review = "Outstanding! Your footprint is extremely low, demonstrating highly sustainable lifestyle habits.";
        } else if (score >= 50) {
            review = "Good work. You are performing better than the average carbon footprint baseline. Check goals to improve further.";
        } else {
            review = "Your footprint exceeds average baselines. Explore the Simulator and AI suggestions to start saving carbon.";
        }
        
        descLbl.textContent = review;
        this.announce(`Your Eco Score has been updated to ${score}. ${review}`);

        // Update progress bar fills
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
     * Renders user badges list highlighting unlocked ones.
     */
    static updateBadges(unlockedBadgesList, badgeConfigs) {
        const grid = this.DOM.badgesGrid || document.getElementById('lst-earned-badges');
        if (!grid) return;
        
        grid.innerHTML = '';
        
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
     * Renders dynamic sustainability coaching bullet points and weekly tasks.
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
        
        // Render bullet point insights
        if (insights.length === 0) {
            insightsList.innerHTML = `<li>No recommendations logged yet. Calculate your footprint above.</li>`;
        } else {
            insights.forEach(ins => {
                const li = document.createElement('li');
                li.textContent = ins;
                insightsList.appendChild(li);
            });
        }
        
        // Render detailed explainable suggestions
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
        
        // Render goals checkcards
        if (weeklyGoals.length === 0) {
            goalsGrid.innerHTML = `<p class="auth-subtitle">No weekly goals available.</p>`;
        } else {
            weeklyGoals.forEach((goal, index) => {
                const card = document.createElement('article');
                card.className = 'goal-card';
                card.setAttribute('aria-labelledby', `goal-title-${index}`);
                
                // Set default impact carbon values for completion logs
                const carbonSavedEstimate = goal.impact === 'High' ? 25.0 : goal.impact === 'Medium' ? 12.0 : 5.0;
                
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
                
                // Add event listener to complete button
                const btn = card.querySelector('.btn-complete');
                btn.addEventListener('click', async (e) => {
                    const title = e.target.getAttribute('data-title');
                    const saved = parseFloat(e.target.getAttribute('data-saved'));
                    e.target.disabled = true;
                    e.target.textContent = "Logged ✓";
                    await completeGoalCallback(title, saved);
                });
                
                goalsGrid.appendChild(card);
            });
        }
    }

    /**
     * Renders lists of prioritized daily, weekly, or monthly action steps.
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
        
        scheduleActions.forEach((action, index) => {
            const li = document.createElement('li');
            li.className = 'action-item';
            
            // Map cost indicators
            const costIcon = action.cost === 'Free' ? '0' : action.cost === 'Low' ? '$' : action.cost === 'Moderate' ? '$$' : '$$$';
            
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
     * Refreshes dashboard scorecard statistics totals.
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
