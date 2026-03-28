# CutCarbon Documentation Hub

Welcome to **CutCarbon** — the AI-powered event carbon accounting platform. This directory contains complete documentation to help you understand, use, and extend the application.

---

## 📚 Documentation Files

### 1. **[QUICK_START.md](QUICK_START.md)** — Start Here! ⭐
**5-minute introduction** | Best for: New users who want to get started immediately

- Login & registration
- Navigate the dashboard
- Create your first scenario (2 ways)
- Get reduction suggestions
- Calculate financial impact
- Common workflows
- Pro tips & keyboard shortcuts

**Read this first if you want to try the app right now.**

---

### 2. **[USER_GUIDE.md](USER_GUIDE.md)** — Complete Manual 📖
**Comprehensive reference** | Best for: Understanding every feature in depth

- **Overview** — What CutCarbon does and its three core power sources
- **Getting Started** — Account creation, dashboard orientation
- **Core Features** — Overview of 7 tabs and their purposes
- **User Journey** — Step-by-step example: plan a tech conference
- **Feature Deep-Dives**:
  - 🤖 AI Co-Pilot (chat with emissions calculator)
  - 📋 Scenarios (create, edit, clone, compare)
  - 💰 Financial Analysis (tax savings, incentives, ROI)
  - 🏆 Carbon Credits (browse projects, purchase, retire)
  - 🛡️ Compliance (GHG Protocol, ISO 20121, SBTi, regional)
  - 📤 Data & Exports (download reports, agent status)
- **Compliance & Standards** — Scope definitions, data quality, benchmarks
- **FAQs & Troubleshooting** — Q&A, common issues, data privacy

**Read this for a thorough understanding of how to use the platform.**

---

### 3. **[FEATURES.md](FEATURES.md)** — Feature Inventory 🎯
**Detailed feature catalog** | Best for: Understanding what's built and what's coming

- **Features Matrix** — All 7 emission categories with data inputs/outputs
- **Scope Classification** — Scope 1, 2, 3 breakdown
- **AI & Automation**:
  - Chat Co-Pilot capabilities (natural language → structured data)
  - TinyFish web scrapers (6 agents updating emission factors daily)
- **Dashboard & Visualization** — KPI cards, charts, benchmarking
- **Scenario Management** — Create, edit, clone, compare workflows
- **Financial Analysis** — Tax savings by region, incentives, ROI
- **Offset Portfolio** — 10+ project types, purchase/retire workflow
- **Compliance & Reporting** — 4 frameworks (GHG, ISO, SBTi, regional)
- **Data & Integration** — API exports, web scraper status
- **Authentication & Access Control** — User management, data isolation
- **Completeness Matrix** — What's implemented vs. future features
- **Data Models** — JSON schema for scenarios & offsets

**Read this to see the complete feature set and roadmap.**

---

### 4. **[ARCHITECTURE.md](ARCHITECTURE.md)** — System Design 🏗️
**Technical architecture & flows** | Best for: Developers, system designers, understanding data flow

- **System Architecture Diagram** — Frontend (React + Vite), Backend (FastAPI), Database, External services
- **Complete User Journey** — Flowchart from login → scenario creation → offset → reporting
- **Data Flow: Chat → Calculation → Result** — Step-by-step breakdown of OpenAI integration
- **Authentication Flow** — Registration, login, JWT tokens, session persistence
- **Emission Factor Data Flow** — How web scrapers update data daily
- **End-to-End Example Timeline** — Real scenario from login to export (12 minutes)

**Read this if you want to understand how the system works internally.**

---

### 5. **[CLAUDE.md](CLAUDE.md)** — Development & Tech Stack 💻
**Developer reference** | Best for: Developers extending the codebase

- Running the application locally
- Environment variables & configuration
- Backend architecture (FastAPI routers)
- Services layer (emissions, financial, AI, agents)
- Data models & schemas
- Frontend technology stack
- Static data files

**Read this to set up development environment or modify code.**

---

## 🎯 Which Document Should I Read?

### I'm a **New User** who wants to try the app
1. Start with **QUICK_START.md** (5 min)
2. Then read relevant sections of **USER_GUIDE.md** as needed

### I'm an **Event Planner** trying to calculate event emissions
1. **QUICK_START.md** → Create your first scenario
2. **USER_GUIDE.md** → Financial & Compliance sections
3. Chat with the AI Co-Pilot for quick answers

### I'm a **Sustainability Manager** auditing compliance
1. **USER_GUIDE.md** → Compliance & Standards section
2. **FEATURES.md** → Compliance & Reporting section
3. Explore the Compliance tab in the app

### I'm a **Developer** extending the codebase
1. **CLAUDE.md** → Setup & architecture
2. **ARCHITECTURE.md** → System design & data flows
3. **FEATURES.md** → Feature matrix for implementation context
4. Read the source code comments

### I'm a **Product Manager** understanding scope
1. **FEATURES.md** → Complete feature catalog & roadmap
2. **USER_GUIDE.md** → Feature deep-dives
3. **ARCHITECTURE.md** → Technical constraints & opportunities

### I want **Quick Reference** while using the app
1. **QUICK_START.md** → Common workflows & tips
2. Check inline tooltips in the app (hover over `?` icons)
3. Open AI Co-Pilot tab to ask questions

---

## 🗂️ File Organization

```
CutCarbon/
├─ DOCUMENTATION.md ............. This file
├─ QUICK_START.md ............... 5-minute intro
├─ USER_GUIDE.md ................ Complete manual (2500+ lines)
├─ FEATURES.md .................. Feature catalog
├─ ARCHITECTURE.md .............. System design & flows
├─ CLAUDE.md .................... Developer reference (in repo)
│
├─ app/
│  ├─ main.py ................... FastAPI app entry
│  ├─ config.py ................. Settings & env vars
│  ├─ models/
│  │  ├─ database.py ............ SQLAlchemy ORM models
│  │  └─ schemas.py ............. Pydantic request/response models
│  ├─ routers/
│  │  ├─ auth.py ................ JWT authentication
│  │  ├─ chat.py ................ OpenAI integration
│  │  ├─ scenarios.py ........... CRUD & comparison
│  │  ├─ financial.py ........... Tax savings & incentives
│  │  ├─ offsets.py ............. Carbon credit portfolio
│  │  ├─ exports.py ............. PDF/Excel/JSON downloads
│  │  └─ agents.py .............. Web scraper triggers
│  ├─ services/
│  │  ├─ emissions_engine.py .... GHG Protocol calculations
│  │  ├─ financial_engine.py .... Tax & ROI calculations
│  │  ├─ openai_service.py ...... Chat & function calling
│  │  └─ tinyfish_agent.py ...... Web scraper orchestration
│  └─ data/
│     ├─ emission_factors.json .. Updated by agents daily
│     ├─ tax_incentives.json .... Regional tax rates
│     └─ carbon_offsets.json .... Offset project catalog
│
├─ frontend/
│  ├─ src/ ...................... React source code
│  ├─ public/ ................... Favicons and static assets
│  └─ dist/ ..................... Built frontend served by FastAPI
│
├─ static/ ...................... Legacy UI fallback during migration
│
├─ tests/ ........................ (None currently, opportunity!)
│
├─ requirements.txt .............. Python dependencies
├─ .env.example .................. Environment variable template
└─ cutcarbon.db .................. SQLite database (local dev)
```

---

## 🚀 Quick Links

**I want to...**

- **Try the app right now** → [QUICK_START.md](QUICK_START.md#-start-here)
- **Learn how to use features** → [USER_GUIDE.md](USER_GUIDE.md)
- **Understand the technology** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **See all available features** → [FEATURES.md](FEATURES.md)
- **Set up for development** → [CLAUDE.md](../CLAUDE.md)
- **Check the API** → `http://localhost:8000/docs` (Swagger)
- **Ask the AI** → Open app → AI Co-Pilot tab → Type your question

---

## 📊 Feature Highlights

| Feature | Status | Learn More |
|---------|--------|------------|
| 🔬 Emission Calculations (7 categories) | ✅ Complete | [FEATURES.md](FEATURES.md#-core-emission-calculation) |
| 🤖 AI Chat Co-Pilot | ✅ Complete | [USER_GUIDE.md](USER_GUIDE.md#-ai-co-pilot-chat-tab) |
| 📋 Scenario Management | ✅ Complete | [USER_GUIDE.md](USER_GUIDE.md#-scenarios-tab) |
| 💰 Financial Analysis | ✅ Complete | [USER_GUIDE.md](USER_GUIDE.md#-financial-tab) |
| 🏆 Carbon Offset Portfolio | ✅ Complete | [USER_GUIDE.md](USER_GUIDE.md#-carbon-credits-tab) |
| 🛡️ Compliance Scoring (4 frameworks) | ✅ Complete | [USER_GUIDE.md](USER_GUIDE.md#-compliance-tab) |
| 📊 Dashboard & Visualization | ✅ Complete | [FEATURES.md](FEATURES.md#-dashboard--visualization) |
| 📤 Data Exports (PDF, Excel, JSON) | ✅ Complete | [USER_GUIDE.md](USER_GUIDE.md#-data--exports-tab) |
| 🌐 Web Scraper Agents (6 sources) | ✅ Complete | [FEATURES.md](FEATURES.md#-tinyfish-web-scrapers-6-agents) |
| 🔐 JWT Authentication | ✅ Complete | [ARCHITECTURE.md](ARCHITECTURE.md#-authentication-flow) |

---

## 🎓 Learning Path

### Beginner (New User)
1. Read **QUICK_START.md** (5 min)
2. Log in to app
3. Create scenario using AI Co-Pilot
4. Click through Dashboard, Scenarios, Financial tabs
5. Try exporting a PDF

**Time: 15 minutes**

### Intermediate (Power User)
1. Read **USER_GUIDE.md** (30 min)
2. Create multiple scenarios
3. Use comparison view
4. Explore all 7 tabs thoroughly
5. Set up carbon offset purchases
6. Review compliance framework scores

**Time: 1-2 hours**

### Advanced (Developer/PM)
1. Read **ARCHITECTURE.md** (30 min)
2. Read **FEATURES.md** (20 min)
3. Read **CLAUDE.md** (20 min)
4. Review source code in relevant routers/services
5. Explore API via Swagger docs
6. Plan enhancements & features

**Time: 2-3 hours**

---

## 🆘 Getting Help

| Question | Where to Look |
|----------|--------------|
| "How do I create a scenario?" | [QUICK_START.md](QUICK_START.md#2-understand-your-dashboard-1-minute) |
| "What does 'Scope 3' mean?" | [USER_GUIDE.md](USER_GUIDE.md#-ghg-protocol-scope-definitions) |
| "How much does offsetting cost?" | [USER_GUIDE.md](USER_GUIDE.md#-carbon-credits-tab) |
| "What compliance frameworks are supported?" | [FEATURES.md](FEATURES.md#-framework-coverage) |
| "How does the AI work?" | [ARCHITECTURE.md](ARCHITECTURE.md#-data-flow-chat--calculation--result) |
| "Can I export my data?" | [USER_GUIDE.md](USER_GUIDE.md#-data--exports-tab) |
| "How often are emission factors updated?" | [FEATURES.md](FEATURES.md#-tinyfish-web-scrapers-6-agents) |
| "Is my data secure?" | [USER_GUIDE.md](USER_GUIDE.md#-data-privacy--security) |

---

## 🔄 Stay Updated

- 📧 Email sustainability@cutcarbon.co for support
- 🐛 Report bugs via GitHub issues
- 💡 Suggest features in discussions
- 📰 Check [FEATURES.md](FEATURES.md#-feature-completeness) for roadmap

---

## 📈 Version History

| Version | Date | Highlights |
|---------|------|-----------|
| 2.0 | 2026-03-28 | AI Co-Pilot, web scrapers, compliance framework, offsets |
| 1.5 | 2026-03-15 | Financial analysis, regional tax calculations |
| 1.0 | 2026-02-28 | Core emissions calculations, scenarios, dashboard |

---

## 📄 License & Attribution

CutCarbon is an educational/demonstration project.

**Data Sources Attributed:**
- ICAO Carbon Emissions Calculator
- UK DEFRA Emission Factors
- European Environment Agency (EMA)
- Singapore National Environment Agency (NEA)
- Ember Climate (electricity grid data)
- Our World in Data (food & general statistics)
- Gold Standard, VCS, ACR (carbon offset projects)

---

## 🎉 Ready to Get Started?

**Recommended next steps:**

1. **If you just want to try it:**
   → Open [QUICK_START.md](QUICK_START.md) and follow the 5-minute guide

2. **If you want to learn thoroughly:**
   → Open [USER_GUIDE.md](USER_GUIDE.md) and read the feature deep-dives

3. **If you want to understand the code:**
   → Open [ARCHITECTURE.md](ARCHITECTURE.md) and [CLAUDE.md](../CLAUDE.md)

4. **If you want to explore the API:**
   → Open terminal → `python create_mock_data.py` → Visit `http://localhost:8000/docs`

5. **If you have questions:**
   → Open the app → Click **AI Co-Pilot** → Ask away! 🤖

---

**Happy carbon accounting! 🌍🌱**

---

*CutCarbon EventCarbon Co-Pilot — Deterministic Emissions. Intelligent Reduction. Verified Offsets.*

Last updated: March 28, 2026
