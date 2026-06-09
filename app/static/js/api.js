/**
 * @fileoverview CarbonWise API Client Wrapper.
 *
 * Provides a centralised, typed interface for every REST API endpoint exposed
 * by the CarbonWise AI backend. All methods delegate to a shared {@link CarbonWiseAPI.request}
 * handler which attaches the required CSRF header, serialises JSON bodies, and
 * converts non-2xx responses into typed JavaScript {@link Error} objects so that
 * callers can use try/catch without inspecting raw status codes.
 *
 * All API methods are {@code static async} and return Promises that resolve to
 * the parsed JSON response body or reject with an augmented Error object that
 * carries {@code error.status} (HTTP status code) and {@code error.code}
 * (application error code from the response envelope).
 */

class CarbonWiseAPI {
    /**
     * Centralised fetch wrapper that applies authentication and CSRF headers.
     *
     * Adds {@code Content-Type: application/json} and the custom
     * {@code X-Requested-With: XMLHttpRequest} CSRF verification header to
     * every request. Serialises object bodies to JSON strings automatically.
     * Converts non-2xx HTTP responses into thrown {@link Error} instances so
     * that callers can catch errors uniformly.
     *
     * @param {string} url - Absolute or relative URL to fetch.
     * @param {RequestInit} [options={}] - Fetch options (method, headers, body).
     * @returns {Promise<Object>} Parsed JSON response body on success.
     * @throws {Error} When the server returns a non-2xx status. The error
     *   object is augmented with {@code status} (HTTP code) and {@code code}
     *   (application error code) properties.
     */
    static async request(url, options = {}) {
        const defaultHeaders = {
            'Content-Type': 'application/json',
            // Custom header CSRF protection — browser cross-origin form posts
            // cannot set arbitrary headers, so its presence proves same-origin intent
            'X-Requested-With': 'XMLHttpRequest'
        };

        options.headers = { ...defaultHeaders, ...options.headers };

        // Auto-serialise plain-object bodies to JSON strings
        if (options.body && typeof options.body === 'object') {
            options.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, options);
            // Use .catch fallback so malformed JSON does not throw an unhandled rejection
            const resData = await response.json().catch(() => ({}));

            if (!response.ok) {
                const message = resData.message || `Request failed with status ${response.status}`;
                const err = new Error(message);
                // Augment the error with HTTP and application-level codes for callers
                err.status = response.status;
                err.code = resData.code;
                throw err;
            }

            return resData;
        } catch (error) {
            console.error(`[API Network Error] ${url}:`, error);
            throw error;
        }
    }

    // ── Authentication Endpoints ─────────────────────────────────────────────

    /**
     * Register a new user account.
     *
     * @param {string} username - Display name (3–30 characters).
     * @param {string} email - Valid email address.
     * @param {string} password - Plain-text password (6–100 characters).
     * @returns {Promise<Object>} Success envelope with {@code user_id}.
     * @throws {Error} When validation fails or the email is already registered.
     */
    static async register(username, email, password) {
        return this.request('/api/auth/register', {
            method: 'POST',
            body: { username, email, password }
        });
    }

    /**
     * Authenticate with existing credentials and establish a session.
     *
     * @param {string} email - Registered email address.
     * @param {string} password - Account password.
     * @returns {Promise<Object>} Success envelope with the user profile document.
     * @throws {Error} When credentials are invalid (401).
     */
    static async login(email, password) {
        return this.request('/api/auth/login', {
            method: 'POST',
            body: { email, password }
        });
    }

    /**
     * Terminate the active session and clear the session cookie.
     *
     * @returns {Promise<Object>} Success envelope with a confirmation message.
     */
    static async logout() {
        return this.request('/api/auth/logout', { method: 'POST' });
    }

    /**
     * Retrieve the authenticated user's profile, streak, and badge list.
     *
     * @returns {Promise<Object>} Success envelope with the profile document,
     *   or a 401 error when no session is active.
     */
    static async getProfile() {
        return this.request('/api/auth/profile', { method: 'GET' });
    }

    // ── Carbon Calculation Endpoints ─────────────────────────────────────────

    /**
     * Submit a monthly carbon footprint calculation for persistence.
     *
     * @param {Object} payload - Validated calculator form data containing
     *   {@code transport}, {@code energy}, {@code food}, and {@code consumption}
     *   sub-objects.
     * @returns {Promise<Object>} Success envelope with the full calculation
     *   document including {@code emissions}, {@code eco_score}, and
     *   {@code newly_awarded_badges}.
     * @throws {Error} When the payload fails server-side validation (400).
     */
    static async calculateFootprint(payload) {
        return this.request('/api/carbon/calculate', {
            method: 'POST',
            body: payload
        });
    }

    /**
     * Retrieve the authenticated user's historical footprint entries.
     *
     * @returns {Promise<Object>} Success envelope with an array of calculation
     *   documents sorted newest-first.
     */
    static async getHistory() {
        return this.request('/api/carbon/history', { method: 'GET' });
    }

    /**
     * Project emission reductions under a hypothetical lifestyle change scenario.
     *
     * @param {Object} payload - Simulation parameters with {@code public_transit_shift},
     *   {@code meat_reduction}, {@code clean_energy_shift} (percentages 0–100),
     *   and a {@code base_footprint} calculator input object.
     * @returns {Promise<Object>} Success envelope with the comparative reduction
     *   analysis including {@code potential_reduction_kg} and {@code projected_score}.
     * @throws {Error} When the payload fails server-side validation (400).
     */
    static async simulateScenario(payload) {
        return this.request('/api/carbon/simulate', {
            method: 'POST',
            body: payload
        });
    }

    /**
     * Request a 30-day and 90-day emission forecast from the AI model.
     *
     * @returns {Promise<Object>} Success envelope with {@code projection_30_days},
     *   {@code projection_90_days}, and {@code reasoning} fields.
     * @throws {Error} When no history is available to base the prediction on (400).
     */
    static async getPredictions() {
        return this.request('/api/carbon/predict', { method: 'GET' });
    }

    // ── AI Coach Endpoints ───────────────────────────────────────────────────

    /**
     * Fetch personalised coaching insights from the Gemini AI model.
     *
     * @returns {Promise<Object>} Success envelope with {@code insights},
     *   {@code suggestions}, and {@code weekly_goals} arrays.
     * @throws {Error} When no footprint history exists (400).
     */
    static async getCoachInsights() {
        return this.request('/api/coach/insights', { method: 'GET' });
    }

    /**
     * Retrieve a structured daily, weekly, and monthly sustainable habit plan.
     *
     * @returns {Promise<Object>} Success envelope with {@code daily}, {@code weekly},
     *   and {@code monthly} action arrays.
     * @throws {Error} When no footprint history exists (400).
     */
    static async getActionPlan() {
        return this.request('/api/coach/plan', { method: 'GET' });
    }

    /**
     * Record a coaching goal as completed and return the updated analytics summary.
     *
     * @param {string} goalTitle - Title of the completed goal.
     * @param {number} carbonSavedKg - Estimated kg CO2e saved by completing the goal.
     * @returns {Promise<Object>} Success envelope with the refreshed analytics summary.
     * @throws {Error} When {@code goalTitle} is missing (400).
     */
    static async completeGoal(goalTitle, carbonSavedKg) {
        return this.request('/api/coach/goals/complete', {
            method: 'POST',
            body: { goal_title: goalTitle, carbon_saved_kg: carbonSavedKg }
        });
    }

    // ── Telemetry Analytics Endpoints ────────────────────────────────────────

    /**
     * Log a frontend interaction event for telemetry collection.
     *
     * @param {string} eventType - One of the allowed event type strings:
     *   {@code "calculator_submitted"}, {@code "goal_completed"},
     *   {@code "simulation_run"}, or {@code "ai_recommendation_accepted"}.
     * @param {Object} metadata - Arbitrary event-specific key-value pairs.
     * @returns {Promise<Object>} Success envelope with a confirmation message.
     * @throws {Error} When the event type is not in the allowed list (400).
     */
    static async trackEvent(eventType, metadata) {
        return this.request('/api/analytics/event', {
            method: 'POST',
            body: { event_type: eventType, metadata }
        });
    }

    /**
     * Retrieve aggregated interaction counts and carbon savings for the dashboard.
     *
     * @returns {Promise<Object>} Success envelope with {@code calculations_run},
     *   {@code goals_completed}, {@code simulations_run},
     *   {@code recommendations_accepted}, and {@code estimated_carbon_saved_kg}.
     */
    static async getTelemetrySummary() {
        return this.request('/api/analytics/summary', { method: 'GET' });
    }
}

/**
 * Creates a debounced version of a function that delays invocation until
 * {@code wait} milliseconds have elapsed since the last call.
 *
 * Used to prevent API flooding when the user rapidly adjusts simulator
 * sliders — each slider movement resets the timer so only the final
 * position triggers a network request.
 *
 * @param {Function} func - The function to debounce.
 * @param {number} wait - Delay in milliseconds before the function is invoked.
 * @returns {Function} Debounced wrapper that resets on each successive call.
 */
function debounce(func, wait) {
    let timeout;
    return function (...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}
