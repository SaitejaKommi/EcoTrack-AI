# CarbonWise AI 🌍

### An AI-powered Personal Carbon Intelligence Platform
*Measure → Understand → Predict → Improve*

---

## 📖 Problem Statement & Overview
Human-induced climate change is driven by greenhouse gas emissions, yet most individuals remain unaware of their personal contribution. While generic carbon calculators exist, they fail to drive long-term habit changes because they lack personalization, predictive forecasting, interactive reduction simulation, and actionable, context-aware steps.

**CarbonWise AI** solves this by creating a SaaS-like intelligence console that calculates, visualizes, predicts, and gamifies carbon footprint tracking. Integrating the **Google Gemini API** with local telemetry logs, CarbonWise AI acts as a personal sustainability strategist, guiding users toward real-world environmental action.

---

## 🛠 Architecture & Technology Stack
CarbonWise AI is designed using a decoupled Service Layer architecture and the Flask Application Factory pattern, ensuring strict separation of concerns, easy testing, and clean data flow.

```
                  ┌─────────────────────────────────────┐
                  │      SPA Client (HTML5/CSS3/JS)     │
                  └──────────────────┬──────────────────┘
                                     │ (JSON REST Requests)
                                     ▼
                  ┌─────────────────────────────────────┐
                  │        Flask API Blueprint          │
                  │    (Auth, Carbon, Coach, Analytics) │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │           Service Layer             │
                  │ (User, Carbon Math, AI, Analytics)  │
                  └──────────┬──────────────────┬───────┘
                             │                  │
                             ▼                  ▼
              ┌─────────────────────┐    ┌──────────────┐
              │    MongoDB Atlas    │    │  Google AI   │
              │ (or JSON DB Backup) │    │  Gemini API  │
              └─────────────────────┘    └──────────────┘
```

*   **Frontend**: Semantic HTML5, Vanilla CSS3 (glassmorphic layouts, micro-animations, HSL themes), Vanilla JavaScript (modular architecture).
*   **Charts**: Chart.js for unified history + forecast visualization.
*   **Backend**: Python Flask (Application Factory, Blueprints).
*   **Database**: MongoDB Atlas with connection-pooling (and local thread-safe JSON Document Store fallback for sandboxed offline evaluation).
*   **Security Stack**: `Flask-Limiter` for request throttling, `Flask-Talisman` for rigid Content Security Policies (CSP) and cookie security, `Werkzeug` for password crypt-hashing.
*   **AI Engine**: Google Gemini API via `google-generativeai` client wrapper (with contextual prompt templates and a local data-driven insight generator fallback).

---

## 🎯 Key Feature Breakdown
1.  **AI Carbon Footprint Calculator**: Captures monthly travel distances, EV details, electricity loads, clean energy usage, food diet scale, and shopping habits. Stores log history to aggregate carbon scorecards.
2.  **AI Sustainability Coach**: Analyzes calculations using the Gemini API. Delivers custom insights, specific suggestions, and structured weekly goals with numeric point rewards based on carbon savings potential.
3.  **Real-Time Carbon Simulator**: Allows users to test "what-if" lifestyle changes (e.g., shifting gasoline commutes to public transit, reducing meat diet ratios, converting grid power to solar). Re-evaluates emissions and updates projections in real-time.
4.  **Smart Action Planner**: Organizes custom habits checklists categorized into Daily, Weekly, and Monthly schedules, prioritized by carbon saving impact, difficulty, and implementation cost.
5.  **Eco Scorecard**: A proprietary 0–100 score model. Scores represent deviation from national carbon averages (50 points = average baseline, higher scores show lower footprints). Weighted categories: Transport (35%), Energy (30%), Food (20%), and Consumption (15%).
6.  **AI Future Prediction Line**: Displays historical carbon emissions alongside dotted AI future trajectory projections (+30 and +90 days) on a single responsive canvas. Includes text explanations detailing predictive factors.
7.  **Gamified Milestones**: Earn badges like *Transit Pioneer*, *Meatless Maestro*, *Eco-Volt*, and *Habit Builder* for active checkins and achievements. Tracks daily streaks dynamically.
8.  **Interaction Analytics**: Telemetry logs monitor calculations logged, simulations run, goals completed, and total kilograms of carbon saved across user sessions.

---

## 🧠 Smart AI Logic & Prompts
CarbonWise AI leverages contextual prompt templates to instruct Gemini to return strictly structured, parser-safe JSON responses, bypassing markdown wrappers:

*   **Explainable AI (XAI)**: Upgraded coaching output to deliver transparent reasoning parameters for every suggestion including `why_chosen` criteria, `estimated_impact` metrics, and expected lifestyle `expected_outcome` blocks.
*   **Insights Prompt**: Injecting user transport variables, home grid numbers, diet type, and shopping habits, the prompt directs Gemini to compute detailed, data-driven action vectors rather than generic tips.
*   **Forecasting Prompt**: Transfers historical data records chronologically to guide the AI in predicting future carbon trends based on active progress logs.
*   **Fallback Engine**: If API keys are omitted or the client runs offline, our localized helper engine dynamically generates user-specific, data-driven advice blocks matching the Gemini API schema structure (with full explainability keys), preventing app failures.

---

## 🗄 Database Design
The application utilizes four key collections:
*   `users`: Handles credentials, creation dates, current streaks, last active dates, and unlocked badges list:
    ```json
    {
      "_id": "ObjectId",
      "username": "EcoWarrior",
      "email": "warrior@carbonwise.com",
      "password_hash": "pbkdf2:sha256...",
      "streak": 5,
      "last_active_date": "2026-06-08",
      "badges": [{"badge_id": "green_diet", "title": "Meatless Maestro", "awarded_at": "..."}]
    }
    ```
*   `calculations`: Stores individual footprint parameters, calculated CO2e category breakdowns, and resulting Eco Scores.
*   `analytics`: Logs client click interactions, telemetry timestamps, and carbon saved.

---

## 🔒 Security Design
*   **CSRF Protection**: Verified custom CSRF protection middleware (`@csrf_protect`) active on all stateful write endpoints, enforcing validation of the `X-Requested-With` request header.
*   **Input Constraints**: Strict boundaries configured at the schema layer to validate max lengths (username max 30, email max 60, password max 100) and restrict calculator parameters to prevent DoS payloads.
*   **Safe Exceptions**: Centralized exception handler intercepts database or api timeouts, serving redacted user-safe JSON errors while preventing system stack trace leakage.
*   **Input Sanitization**: Reusable schemas validate boundaries and strip HTML/Script tags to defend against injection attacks.
*   **API Rate Limiting**: Limiters restrict requests per client IP address (`100/hour`, `10/minute`) on API blueprints to mitigate DDoS threats.
*   **HTTP Talisman Headers**:
    *   Enforces HSTS (HTTP Strict Transport Security) in non-test mode.
    *   Forces frame-ancestors to `'none'` to prevent clickjacking.
    *   Content Security Policy (CSP) locks resources to local scripts and CDNs like Chart.js.
*   **Safe Sessions**: Session identification is held in an encrypted, HTTPOnly, and Secure cookie managed by Flask server keys.

---

## ♿ Accessibility Compliance (WCAG 2.1 AA)
*   **Semantic Landmarks**: Uses `<header>`, `<nav>`, `<main>`, `<section>`, and `<footer>` tags to allow screen reader navigation.
*   **Keyboard Control & Focus Rings**: Fully visible high-contrast focus rings mapped across interactive elements (cards, buttons, tabs) and custom range slider inputs (`.slider-input:focus-visible`) to optimize keyboard tab flows.
*   **ARIA Live Regions**: Announcer region (`#a11y-announcer`) updates verbally on calculator logs, simulator changes, and goal completions.
*   **Accessibility Controls Toolbar**: Dedicated utility bar providing High Contrast Theme toggle, Reduced Motion class override (disables transitions), and text scaling controls (+/- 40%).

---

## 🧪 Testing Strategy
Our testing setup covers service math, route guards, session updates, and validators. Mock interfaces isolate DB and Gemini API calls to enforce consistent test outcomes.
*   Run the test suite with coverage reporting:
    ```bash
    pytest --cov=app tests/
    ```

---

## 🚀 Deployment & Local Run Instructions
1.  **Clone the workspace** and navigate to the project directory.
2.  **Create a python virtual environment**:
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```
3.  **Install requirements**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create your configuration environment** using the variables documented below in `.env`.
5.  **Run the application server**:
    ```bash
    python run.py
    ```
    Open your browser to [http://127.0.0.1:5000](http://127.0.0.1:5000).

### ☁️ Cloud Production Deployment
*   **Render (Blueprint Web Service)**: Automatic builds configured in `render.yaml`. Deploys utilizing Gunicorn via the production WSGI server script (`wsgi.py`).
*   **Vercel (Serverless Functions)**: Built-in routing model config template prepared in `vercel.json` employing `@vercel/python`.

---

## ⚙️ Environment Variables
The application supports the following environment configurations:
*   `SECRET_KEY`: Standard secret salt key used to encrypt user sessions. (Default: `default-insecure-dev-key-carbonwise-ai`)
*   `FLASK_ENV`: Deployment mode (`development` or `production`). Mutes error stack trace leakages in production.
*   `HOST` / `PORT`: Binding interfaces for local dev execution. (Default: `127.0.0.1:5000`)
*   `MONGO_URI`: MongoDB Atlas connection string. If left blank or disconnected, the system falls back to the thread-safe JSON Document Store (`local_db.json`).
*   `GEMINI_API_KEY`: API key for Google Generative AI. If left blank or offline, the system falls back to a rules-based sustainability coach advisory engine.

---

## 📌 Assumptions & Constants
*   **Carbon Emission Coefficients**:
    *   Gasoline vehicle transit: `0.220 kg CO2e / km`
    *   Electric vehicle (EV) transit: `0.050 kg CO2e / km`
    *   Public transit: `0.040 kg CO2e / km`
    *   Flight travel: `0.180 kg CO2e / km`
    *   Grid electricity loads: `0.475 kg CO2e / kWh`
    *   Clean/Solar power: `0.020 kg CO2e / kWh`
*   **Eco Score Scaling**: Score ranges from 0 to 100. A score of 50 represents the national/regional average baseline carbon footprint. Scores higher than 50 indicate a lower footprint (greener lifestyle), while scores below 50 reflect higher emissions than average.
*   **Weekly Goal Metrics**: Interactive targets award users with 10 to 30 gamified points depending on the goal's carbon reduction impact tier.

---

## 🔮 Future Roadmap & Improvements
*   **Smart Home API Integrations**: Sync electrical consumption parameters directly via smart home plugs.
*   **Local Eco-Offsets Marketplace**: Redeem earned gamified points for local tree-planting initiatives.
*   **Community Footprint Teams**: Establish collective carbon pools to compete in city-wide reduction challenges.
