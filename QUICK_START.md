# CutCarbon — Quick Start Guide (5 Minutes)

## 🚀 Start Here

## 💻 Run Locally

For the current React app, use one of these workflows:

```bash
# Backend + FastAPI-served React build
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
uvicorn app.main:app --reload --port 8000

# React development server (optional, in a second terminal)
cd frontend
npm run dev
```

- Open `http://localhost:8000` to use the backend with the built React app.
- Open `http://localhost:5173` for live React development against the local API.
- Open `http://localhost:8000/docs` for Swagger.

### 1. Login / Register (30 seconds)

```
Visit: http://localhost:8000
Email: your@email.com
Password: ••••••••
[Register or Login]
```

---

## 2. Understand Your Dashboard (1 minute)

After login, you land on the **Dashboard** tab. You'll see:

```
┌─────────────────────────────────────────────┐
│  PORTFOLIO OVERVIEW                         │
├─────────────────────────────────────────────┤
│                                             │
│  📊 Total Emissions: 22,745 tCO2e           │
│  💰 Carbon Tax Liability: $908k USD         │
│  🛡️  Compliance Score: 88%                  │
│  🌱 Offset Coverage: 65%                    │
│                                             │
│  BY CATEGORY (pie chart)                    │
│  🔵 Travel: 60%                             │
│  🟢 Venue Energy: 15%                       │
│  🟠 Accommodation: 10%                      │
│  🔴 Catering: 12%                           │
│  🟣 Waste: 2%                               │
│  🩷 Equipment/Swag: 1%                      │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 3. Create Your First Scenario (2 minutes)

### Option A: Chat (Fastest)

Click the **AI Co-Pilot** tab:

```
You type:
"Plan a 500-person tech conference in Singapore
for 2 days. Half from US (flights), half from
Asia (regional flights/train). Vegan catering."

[Hit Enter]

Co-Pilot replies:
"Got it! I see:
 • 500 attendees
 • 2 days
 • 250 from US (~13,600 km flights, economy)
 • 250 from Asia (~3,000 km flights + trains)
 • 100% vegan meals

Calculating...
Result: 1,245 tCO2e total | 2.49 tCO2e/attendee

Would you like me to suggest reductions?"
```

### Option B: Manual Form (Most Control)

Click **Scenarios** tab → **+ New Scenario**

Fill in:
- **Event details**: Name, type, location, attendees, days
- **Travel**: How many people fly? Train? Car?
- **Venue**: Energy consumption, renewable %
- **Accommodation**: Type, room nights
- **Catering**: Meal type (vegan? red meat?), count
- **Waste/Equipment**: Minimal details needed

Click **Calculate** → Results appear instantly.

---

## 4. Review Results (30 seconds)

You'll see:

```
TOTAL EMISSIONS: 1,245 tCO2e
Per attendee: 2.49 tCO2e
Per attendee/day: 1.25 tCO2e

Breakdown:
  Travel: 747 tCO2e (60%)
  Venue Energy: 186 tCO2e (15%)
  Accommodation: 149 tCO2e (12%)
  Catering: 149 tCO2e (12%)
  Waste: 14 tCO2e (1%)

Benchmark: ABOVE AVERAGE (high travel impact)
Data quality: ESTIMATED (could be improved)
```

---

## 5. Get Reduction Suggestions (1 minute)

Click **Get Suggestions** on your scenario:

```
TOP OPPORTUNITIES:

✓ Reduce flights by 20% (more train/virtual)
  Impact: -149 tCO2e (-12%)

✓ Increase renewable venue energy to 80%
  Impact: -37 tCO2e (-3%)

✓ Serve vegan for 50% of attendees
  Impact: -37 tCO2e (-3%)

✓ Digital-first materials (no printed)
  Impact: -7 tCO2e (-1%)

Total potential reduction: -230 tCO2e (-18%)
New total: 1,015 tCO2e
New per-attendee: 2.03 tCO2e
```

Click any suggestion to auto-update your scenario.

---

## 6. Check Financial Impact (1 minute)

Click **Financial** tab → Select your scenario:

```
TAX SAVINGS (Singapore example):

Baseline: 1,245 tCO2e × $25 = $31,125
After reduction: 1,015 tCO2e × $25 = $25,375
TAX SAVINGS: $5,750

INCENTIVES:
  Green venue certification rebate: $5,000
  Carbon neutral event badge: $2,000
  ESG score improvement: $3,000

TOTAL BENEFITS: $15,750 USD

OFFSET COST:
  1,015 tCO2e × $12/tCO2e = $12,180

NET BENEFIT: $3,570 saved vs baseline
(After offset, your event is CARBON NEUTRAL ✓)
```

---

## 7. Offset Your Emissions (1 minute)

Click **Carbon Credits** tab:

```
RECOMMENDED OFFSET MIX:

1. Renewable Energy (India Solar)
   → 600 tCO2e @ $9/tCO2e = $5,400

2. Forestry (Indonesia Reforestation)
   → 300 tCO2e @ $13/tCO2e = $3,900

3. Cookstove (Rwanda)
   → 115 tCO2e @ $5/tCO2e = $575

TOTAL: 1,015 tCO2e | $9,875 cost

[Purchase All] [Retire Credits]
```

After purchase:
- Credits appear in your portfolio
- You own the environmental benefit
- Click **Retire** to claim carbon neutrality for this event

---

## 8. Export Report (30 seconds)

Click **Data & Exports** tab:

```
EXPORT OPTIONS:

[PDF] → Share with stakeholders (pretty charts, summary)
[Excel] → Deep analysis (all calculations, inputs)
[JSON] → Developer import (API integration)

Also shows:
✓ Web scraper agent status
✓ Last emission factor updates
✓ Data quality scores
```

---

## 🎯 Common Workflows

### "I want to plan an event carbon-neutral"

1. **Create scenario** (chat or manual)
2. **Get reductions** (AI suggestions)
3. **Implement** (edit travel, venue, catering)
4. **Calculate offset cost** (financial tab)
5. **Purchase offsets** (carbon credits tab)
6. **Retire credits** (claim carbon neutral)
7. **Export report** (share with team)

**Time: ~10 minutes**

---

### "I want to compare 2 scenarios"

1. **Create scenario 1** (baseline)
2. **Clone scenario 1** → **Create scenario 2** (optimized)
3. Edit scenario 2 with improvements
4. Click **Compare**
5. See side-by-side metrics
6. Export comparison as PDF

**Time: ~5 minutes**

---

### "I want to understand my carbon liability"

1. Go to **Dashboard**
2. View aggregate emissions across all events
3. Click **Financial** tab
4. See tax liability by region
5. Identify highest-impact category
6. Drill into **Compliance** tab
7. Export compliance report

**Time: ~3 minutes**

---

## 💡 Pro Tips

### Tip 1: Use Chat for Brainstorming
Chat is fastest for "what-if" questions:
- "What if we moved to a hybrid format?"
- "How much would switching to vegan save us?"
- "If we do 50% virtual, what's the new footprint?"

### Tip 2: Clone Scenarios for Comparison
Don't create from scratch. Clone, modify, compare.
```
Scenario A: Baseline (all attendees present)
Scenario B: Hybrid (30% virtual)
Scenario C: Greener (vegan + train focus)

Compare all 3 side-by-side to see trade-offs.
```

### Tip 3: Verify Data Quality
- Basic mode = estimates (fast)
- Advanced mode = detailed inputs (more accurate)

To improve quality:
- Get real energy data from venue
- Ask catering for carbon footprint
- Use actual flight bookings (not estimates)

### Tip 4: Check Benchmarks
Each scenario shows how you rank vs. industry:
- "Above average" = high impact (opportunity for improvement)
- "Average" = typical for your event type
- "Below average" / "Best practice" = excellent!

### Tip 5: Track Agent Updates
Emission factors update daily via web scrapers.
- Check **Data & Exports** to see what changed
- Old calculations are always re-calculated with latest data
- You'll never have stale factors

---

## ⚡ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Tab` key | Navigate between form fields |
| `Enter` | Submit chat message |
| `Esc` | Close modal dialogs |
| `Ctrl/Cmd + S` | Export current scenario |

---

## 🔗 Navigation Map

```
DASHBOARD (Home)
├─ Overview of all scenarios
├─ Aggregate KPIs
└─ Quick links to other tabs

AI CO-PILOT
├─ Chat with AI
├─ Get suggestions
└─ Auto-create scenarios

SCENARIOS
├─ Create new
├─ Edit existing
├─ Clone for "what-if"
├─ Compare side-by-side
└─ View breakdown charts

FINANCIAL
├─ Calculate tax savings
├─ View incentives
├─ Estimate ROI
└─ Compliance value

CARBON CREDITS
├─ Browse offset projects
├─ Track portfolio
├─ Purchase credits
├─ Retire for carbon neutral

COMPLIANCE
├─ GHG Protocol score
├─ ISO 20121 checklist
├─ SBTi progress
└─ Regional regulation status

DATA & EXPORTS
├─ Download PDF/Excel/JSON
├─ View web scraper status
└─ Check emission factor history
```

---

## 🆘 Quick Help

| Problem | Solution |
|---------|----------|
| Chat doesn't understand my input | Be specific: mention attendee count, locations, duration |
| Emissions seem too high | Check travel mode + attendee count. Flights dominate! |
| Can't find my scenario | Use Dashboard to see all. Search by name. |
| Want to edit scenario | Click Edit button. Changes recalculate instantly. |
| Export not working | Try different format. Check browser downloads. |
| Data seems outdated | Check Data & Exports. Agents refresh daily. |

---

## 📚 Next Steps

✅ **Now you can:**
- Calculate event emissions in < 2 minutes
- Find reduction opportunities
- Estimate financial impact
- Offset your event carbon-neutral

📖 **For detailed help:**
- Read [USER_GUIDE.md](USER_GUIDE.md) (comprehensive manual)
- Check inline tooltips (hover over `?` icons)
- Review [CLAUDE.md](CLAUDE.md) (technical architecture)

💬 **For AI help:**
- Open **AI Co-Pilot** tab and ask anything
- AI knows your event context and suggests improvements
- Get reduction ideas in plain English

---

**Ready to offset your event? Let's go! 🌍**
