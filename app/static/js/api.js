/**
 * CarbonWise API Client Wrapper
 * Handles network transactions, error decoding, and request debouncing.
 */

class CarbonWiseAPI {
    /**
     * Centralized network request handler.
     */
    static async request(url, options = {}) {
        const defaultHeaders = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        };
        
        options.headers = {
            ...defaultHeaders,
            ...options.headers
        };
        
        if (options.body && typeof options.body === 'object') {
            options.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, options);
            const resData = await response.json().catch(() => ({}));
            
            if (!response.ok) {
                const message = resData.message || `Request failed with status ${response.status}`;
                const err = new Error(message);
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

    // --- AUTHENTICATION ENDPOINTS ---
    static async register(username, email, password) {
        return this.request('/api/auth/register', {
            method: 'POST',
            body: { username, email, password }
        });
    }

    static async login(email, password) {
        return this.request('/api/auth/login', {
            method: 'POST',
            body: { email, password }
        });
    }

    static async logout() {
        return this.request('/api/auth/logout', { method: 'POST' });
    }

    static async getProfile() {
        return this.request('/api/auth/profile', { method: 'GET' });
    }

    // --- CARBON LOGGING ENDPOINTS ---
    static async calculateFootprint(payload) {
        return this.request('/api/carbon/calculate', {
            method: 'POST',
            body: payload
        });
    }

    static async getHistory() {
        return this.request('/api/carbon/history', { method: 'GET' });
    }

    static async simulateScenario(payload) {
        return this.request('/api/carbon/simulate', {
            method: 'POST',
            body: payload
        });
    }

    static async getPredictions() {
        return this.request('/api/carbon/predict', { method: 'GET' });
    }

    // --- AI COACH ENDPOINTS ---
    static async getCoachInsights() {
        return this.request('/api/coach/insights', { method: 'GET' });
    }

    static async getActionPlan() {
        return this.request('/api/coach/plan', { method: 'GET' });
    }

    static async completeGoal(goalTitle, carbonSavedKg) {
        return this.request('/api/coach/goals/complete', {
            method: 'POST',
            body: { goal_title: goalTitle, carbon_saved_kg: carbonSavedKg }
        });
    }

    // --- TELEMETRY ANALYTICS ENDPOINTS ---
    static async trackEvent(eventType, metadata) {
        return this.request('/api/analytics/event', {
            method: 'POST',
            body: { event_type: eventType, metadata }
        });
    }

    static async getTelemetrySummary() {
        return this.request('/api/analytics/summary', { method: 'GET' });
    }
}

/**
 * Debounce utility to prevent API flooding during slider updates
 */
function debounce(func, wait) {
    let timeout;
    return function (...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}
