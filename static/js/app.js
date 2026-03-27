// EventCarbon Co-Pilot — Alpine.js application logic
// All API calls go through the FastAPI backend

const API = '';  // same origin

function app() {
  return {
    // ── Nav ─────────────────────────────────────────────────────────────────
    activeTab: 'dashboard',
    navItems: [
      { id: 'dashboard',  label: 'Dashboard',   icon: 'fas fa-chart-line',       desc: 'Overview of your carbon footprint and savings' },
      { id: 'chat',       label: 'AI Co-Pilot',  icon: 'fas fa-robot',            desc: 'Chat with the AI to build and analyse scenarios' },
      { id: 'scenarios',  label: 'Scenarios',    icon: 'fas fa-layer-group',      desc: 'Create, compare and clone emission scenarios' },
      { id: 'financial',  label: 'Financial',    icon: 'fas fa-coins',            desc: 'Carbon tax savings, incentives and ROI calculator' },
      { id: 'compliance', label: 'Compliance',   icon: 'fas fa-shield-halved',    desc: 'GHG Protocol, ISO 20121, SBTi and regional compliance' },
    ],
    quickActions: [],

    // ── Shared state ─────────────────────────────────────────────────────────
    scenarios: [],
    selectedScenario: null,
    suggestions: [],
    toast: { show: false, message: '', icon: 'fas fa-check text-accent' },
    agentsRunning: false,

    // ── Dashboard ─────────────────────────────────────────────────────────────
    bestScenario: null,
    potentialSavings: null,
    complianceScore: null,
    categoryChart: null,
    comparisonChart: null,
    pathwayChart: null,

    emissionCategories: [
      { key: 'travel_tco2e',           label: '✈ Travel',        color: '#4fc3f7' },
      { key: 'venue_energy_tco2e',     label: '⚡ Venue Energy',  color: '#00d68f' },
      { key: 'accommodation_tco2e',    label: '🏨 Accommodation', color: '#ffd600' },
      { key: 'catering_tco2e',         label: '🍽 Catering',      color: '#ff9800' },
      { key: 'materials_waste_tco2e',  label: '♻ Waste',          color: '#e040fb' },
    ],

    // ── Chat ─────────────────────────────────────────────────────────────────
    chatMessages: [],
    chatInput: '',
    chatLoading: false,
    chatSuggestions: [],
    chatContext: {},
    lastExtracted: null,
    sessionId: 'session-' + Math.random().toString(36).slice(2, 9),
    startSuggestions: [
      '🌏 Plan a 3-day tech conference in Singapore, 500 attendees, hybrid',
      '✈ Estimate emissions for 200 delegates flying from Europe to London',
      '🥗 What\'s the carbon impact of switching our gala dinner to vegan?',
    ],

    // ── Scenarios ────────────────────────────────────────────────────────────
    scenarioLoading: false,
    newScenario: {
      name: '',
      attendees: 300,
      event_days: 2,
      location: 'Singapore',
      venue_grid: 'singapore',
      catering_type: 'mixed_buffet',
      accommodation_type: 'standard_hotel',
      renewable_pct: 0,
      travel_segments: [],
    },

    // ── Financial ────────────────────────────────────────────────────────────
    finCalc: {
      region: 'singapore',
      baseline: 50,
      reduction_pct: 30,
      energy_kwh: 0,
      meal_switches: 0,
      actions: [],
    },
    finResult: null,
    finLoading: false,
    availableActions: [
      { key: 'renewable_energy',     label: '⚡ Renewable energy' },
      { key: 'vegetarian_menu',      label: '🥗 Vegetarian menu' },
      { key: 'digital_materials',    label: '📱 Digital materials' },
      { key: 'hybrid_event',         label: '💻 Hybrid/virtual option' },
      { key: 'ghg_reporting',        label: '📋 GHG reporting' },
      { key: 'carbon_audit',         label: '🔍 Carbon audit' },
      { key: 'sustainability_audit', label: '✅ Sustainability audit' },
    ],

    // ── Compliance ────────────────────────────────────────────────────────────
    complianceInput: {
      region: 'singapore',
      total_tco2e: 50,
      attendees: 300,
      event_days: 2,
      has_scope3: true,
      has_ghg_report: false,
    },
    complianceReport: null,
    complianceLoading: false,

    // ── Init ──────────────────────────────────────────────────────────────────
    async init() {
      this.quickActions = [
        { icon: '🤖', title: 'Ask the Co-Pilot', desc: 'Describe your event in plain English', handler: () => this.activeTab = 'chat' },
        { icon: '📊', title: 'Build a Scenario', desc: 'Fill in the structured form', handler: () => this.activeTab = 'scenarios' },
        { icon: '💰', title: 'Calculate Savings', desc: 'See carbon tax & incentive benefits', handler: () => this.activeTab = 'financial' },
      ];
      await this.loadScenarios();
    },

    // ── Toast ─────────────────────────────────────────────────────────────────
    showToast(message, icon = 'fas fa-check text-accent') {
      this.toast = { show: true, message, icon };
      setTimeout(() => this.toast.show = false, 3500);
    },

    // ── Scenarios ─────────────────────────────────────────────────────────────
    async loadScenarios() {
      try {
        const res = await fetch(`${API}/api/scenarios`);
        this.scenarios = await res.json();
        if (this.scenarios.length > 0) {
          this.bestScenario = [...this.scenarios].sort(
            (a, b) => a.emissions.total_tco2e - b.emissions.total_tco2e
          )[0];
          if (!this.selectedScenario) this.selectedScenario = this.scenarios[0];
          this.$nextTick(() => this.drawCharts());
          // Rough potential savings: 30% of best scenario at $25 SGD/tCO2e → USD
          this.potentialSavings = Math.round(this.bestScenario.emissions.total_tco2e * 0.3 * 25 * 0.74);
        }
      } catch (e) {
        console.error(e);
      }
    },

    async calculateScenario() {
      this.scenarioLoading = true;
      try {
        const payload = this._buildScenarioPayload();
        const res = await fetch(`${API}/api/scenarios`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(await res.text());
        const scenario = await res.json();
        this.scenarios.unshift(scenario);
        this.selectedScenario = scenario;
        this.bestScenario = [...this.scenarios].sort(
          (a, b) => a.emissions.total_tco2e - b.emissions.total_tco2e
        )[0];
        this.newScenario.name = '';
        this.newScenario.travel_segments = [];
        this.showToast(`Scenario "${scenario.name}" calculated: ${scenario.emissions.total_tco2e.toFixed(2)} tCO₂e`);
        this.$nextTick(() => this.drawCharts());

        // Update compliance score with quick check
        this.complianceScore = Math.round(50 + (scenario.emissions.per_attendee_tco2e < 0.5 ? 30 : 0));
      } catch (e) {
        this.showToast('Error: ' + e.message, 'fas fa-triangle-exclamation text-red');
      } finally {
        this.scenarioLoading = false;
      }
    },

    _buildScenarioPayload() {
      const ns = this.newScenario;
      const payload = {
        name: ns.name || 'Scenario ' + (this.scenarios.length + 1),
        event_name: ns.location + ' Event',
        location: ns.location,
        attendees: ns.attendees,
        event_days: ns.event_days,
        mode: 'basic',
        venue_energy: {
          grid_region: ns.venue_grid,
          renewable_pct: ns.renewable_pct,
        },
        catering: {
          catering_type: ns.catering_type,
          meals: ns.attendees * ns.event_days * 2,
          include_beverages: true,
        },
        accommodation: {
          accommodation_type: ns.accommodation_type,
          room_nights: Math.ceil(ns.attendees * 0.8 / 1.5) * ns.event_days,
        },
      };

      if (ns.travel_segments && ns.travel_segments.length > 0) {
        payload.travel_segments = ns.travel_segments.map(seg => ({
          mode: seg.mode,
          travel_class: 'economy',
          attendees: seg.attendees || 50,
          distance_km: seg.distance_km || 500,
          label: seg.mode,
        }));
      }
      return payload;
    },

    async cloneScenario(scenario) {
      const name = prompt('Name for cloned scenario:', 'Copy of ' + scenario.name);
      if (!name) return;
      try {
        const res = await fetch(`${API}/api/scenarios/${scenario.scenario_id}/clone?name=${encodeURIComponent(name)}`, {
          method: 'POST',
        });
        const cloned = await res.json();
        this.scenarios.unshift(cloned);
        this.showToast('Scenario cloned: ' + name);
        this.$nextTick(() => this.drawCharts());
      } catch (e) {
        this.showToast('Clone failed', 'fas fa-triangle-exclamation text-red');
      }
    },

    async deleteScenario(id) {
      if (!confirm('Delete this scenario?')) return;
      await fetch(`${API}/api/scenarios/${id}`, { method: 'DELETE' });
      this.scenarios = this.scenarios.filter(s => s.scenario_id !== id);
      if (this.selectedScenario?.scenario_id === id) this.selectedScenario = this.scenarios[0] || null;
      this.suggestions = [];
      this.showToast('Scenario deleted');
      this.$nextTick(() => this.drawCharts());
    },

    selectScenario(s) {
      this.selectedScenario = s;
      this.suggestions = [];
      // Pre-populate financial calc
      this.finCalc.baseline = s.emissions.total_tco2e;
      this.complianceInput.total_tco2e = s.emissions.total_tco2e;
      this.complianceInput.attendees = s.attendees;
      this.complianceInput.event_days = s.event_days;
      this.$nextTick(() => this.drawCharts());
    },

    async getSuggestions(scenario) {
      try {
        const res = await fetch(`${API}/api/scenarios/${scenario.scenario_id}/suggestions?target_pct=30`);
        this.suggestions = await res.json();
        this.showToast('Reduction suggestions loaded');
      } catch (e) {
        this.showToast('Failed to load suggestions', 'fas fa-triangle-exclamation text-red');
      }
    },

    addTravelSegment() {
      this.newScenario.travel_segments.push({
        mode: 'long_haul_flight',
        attendees: 100,
        distance_km: 2000,
      });
    },

    // ── Charts ───────────────────────────────────────────────────────────────
    drawCharts() {
      this.drawCategoryChart();
      this.drawComparisonChart();
      if (this.selectedScenario) this.drawPathwayChart();
    },

    drawCategoryChart() {
      const s = this.selectedScenario;
      if (!s) return;
      const ctx = document.getElementById('categoryChart');
      if (!ctx) return;
      if (this.categoryChart) this.categoryChart.destroy();

      const labels = this.emissionCategories.map(c => c.label);
      const data = this.emissionCategories.map(c => s.emissions[c.key] * 1000);
      const colors = this.emissionCategories.map(c => c.color);

      this.categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels,
          datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 8 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#90a4ae', font: { size: 11 }, boxWidth: 12 },
            },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.label}: ${(ctx.raw / 1000).toFixed(3)} tCO₂e (${((ctx.raw / data.reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%)`,
              },
            },
          },
        },
      });
    },

    drawComparisonChart() {
      const ctx = document.getElementById('comparisonChart');
      if (!ctx || this.scenarios.length === 0) return;
      if (this.comparisonChart) this.comparisonChart.destroy();

      const cats = this.emissionCategories;
      const colors = cats.map(c => c.color);
      const labels = this.scenarios.slice(0, 6).map(s => s.name);

      const datasets = cats.map((cat, i) => ({
        label: cat.label,
        data: this.scenarios.slice(0, 6).map(s => s.emissions[cat.key] * 1000),
        backgroundColor: cat.color + 'cc',
        borderRadius: 4,
      }));

      this.comparisonChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { stacked: true, ticks: { color: '#90a4ae', font: { size: 10 } }, grid: { color: '#1a3a2a' } },
            y: {
              stacked: true,
              ticks: { color: '#90a4ae', font: { size: 10 }, callback: v => v.toFixed(0) + ' kg' },
              grid: { color: '#1a3a2a' },
            },
          },
          plugins: {
            legend: { labels: { color: '#90a4ae', font: { size: 10 }, boxWidth: 10 } },
          },
        },
      });
    },

    drawPathwayChart() {
      const s = this.selectedScenario;
      if (!s) return;
      const ctx = document.getElementById('pathwayChart');
      if (!ctx) return;
      if (this.pathwayChart) this.pathwayChart.destroy();

      const base = s.emissions.total_tco2e;
      const years = [2024, 2026, 2028, 2030, 2035, 2040, 2050];
      // Linear reduction to net-zero by 2050
      const pathway = years.map(y => +(base * Math.max(0, 1 - (y - 2024) / 26)).toFixed(3));
      // SBTi 1.5°C budget line
      const sbti = years.map(y => +(base * Math.max(0, 1 - (y - 2024) / 26 * 1.3)).toFixed(3));

      this.pathwayChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: years,
          datasets: [
            {
              label: 'Your pathway',
              data: pathway,
              borderColor: '#00d68f',
              backgroundColor: 'rgba(0,214,143,0.08)',
              fill: true,
              tension: 0.4,
              pointBackgroundColor: '#00d68f',
            },
            {
              label: 'SBTi 1.5°C budget',
              data: sbti,
              borderColor: '#ffd600',
              borderDash: [5, 5],
              backgroundColor: 'transparent',
              tension: 0.4,
              pointRadius: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { ticks: { color: '#90a4ae' }, grid: { color: '#1a3a2a' } },
            y: {
              ticks: { color: '#90a4ae', callback: v => v + ' t' },
              grid: { color: '#1a3a2a' },
            },
          },
          plugins: {
            legend: { labels: { color: '#90a4ae', font: { size: 11 } } },
          },
        },
      });
    },

    // ── Chat ─────────────────────────────────────────────────────────────────
    async sendChat() {
      const text = this.chatInput.trim();
      if (!text) return;
      this.chatInput = '';
      this.chatMessages.push({ role: 'user', content: text });
      this.chatLoading = true;
      this.$nextTick(() => this.scrollChat());

      try {
        const messages = this.chatMessages.map(m => ({ role: m.role, content: m.content }));
        const res = await fetch(`${API}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages,
            event_context: { ...this.chatContext, session_id: this.sessionId },
          }),
        });
        const data = await res.json();

        const botMsg = {
          role: 'assistant',
          content: data.reply,
          extracted_data: data.extracted_data,
        };
        this.chatMessages.push(botMsg);
        this.chatSuggestions = data.suggestions || [];

        if (data.extracted_data) {
          this.lastExtracted = data.extracted_data;
          // Update context
          if (data.extracted_data.attendees) this.chatContext.attendees = data.extracted_data.attendees;
          if (data.extracted_data.event_name) this.chatContext.event_name = data.extracted_data.event_name;
          if (data.extracted_data.location) this.chatContext.location = data.extracted_data.location;
        }
      } catch (e) {
        this.chatMessages.push({ role: 'assistant', content: 'Sorry, I encountered an error. Please check your API key and try again.' });
      } finally {
        this.chatLoading = false;
        this.$nextTick(() => this.scrollChat());
      }
    },

    sendSuggestion(text) {
      this.chatInput = text;
      this.sendChat();
    },

    scrollChat() {
      const el = document.getElementById('chatMessages');
      if (el) el.scrollTop = el.scrollHeight;
    },

    formatMessage(text) {
      // Basic markdown: **bold**, `code`, newlines
      return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code style="background:var(--green-900);padding:1px 5px;border-radius:4px;font-family:monospace">$1</code>')
        .replace(/\n/g, '<br>');
    },

    applyExtracted(data) {
      if (data.attendees) this.newScenario.attendees = data.attendees;
      if (data.event_days) this.newScenario.event_days = data.event_days;
      if (data.location) this.newScenario.location = data.location;
      if (data.venue_grid_region) this.newScenario.venue_grid = data.venue_grid_region;
      if (data.catering_type) this.newScenario.catering_type = data.catering_type;
      if (data.accommodation_type) this.newScenario.accommodation_type = data.accommodation_type;
      if (data.renewable_pct !== undefined) this.newScenario.renewable_pct = data.renewable_pct;
      if (data.travel_segments) this.newScenario.travel_segments = data.travel_segments;
      this.activeTab = 'scenarios';
      this.showToast('Data applied to scenario builder');
    },

    buildScenarioFromExtracted() {
      if (!this.lastExtracted) return;
      this.applyExtracted(this.lastExtracted);
    },

    // ── Financial ─────────────────────────────────────────────────────────────
    async calculateSavings() {
      this.finLoading = true;
      try {
        const reduced = this.finCalc.baseline * (1 - this.finCalc.reduction_pct / 100);
        const res = await fetch(`${API}/api/financial/savings`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            baseline_tco2e: this.finCalc.baseline,
            reduced_tco2e: reduced,
            region: this.finCalc.region,
            energy_kwh_saved: this.finCalc.energy_kwh || 0,
            meal_switches: this.finCalc.meal_switches || 0,
            attendees: this.complianceInput.attendees || 0,
            actions_taken: this.finCalc.actions,
          }),
        });
        this.finResult = await res.json();
        this.potentialSavings = Math.round(this.finResult.total_financial_savings_usd);
        this.showToast(`Total savings: $${this.finResult.total_financial_savings_usd.toLocaleString()}`);
      } catch (e) {
        this.showToast('Calculation error: ' + e.message, 'fas fa-triangle-exclamation text-red');
      } finally {
        this.finLoading = false;
      }
    },

    // ── Compliance ────────────────────────────────────────────────────────────
    async checkCompliance() {
      this.complianceLoading = true;
      try {
        const p = this.complianceInput;
        const url = `${API}/api/financial/compliance?total_tco2e=${p.total_tco2e}&has_scope3=${p.has_scope3}&has_ghg_report=${p.has_ghg_report}&region=${p.region}&event_days=${p.event_days}&attendees=${p.attendees}`;
        const res = await fetch(url, { method: 'POST' });
        this.complianceReport = await res.json();
        this.complianceScore = Math.round(this.complianceReport.overall_score_pct);
        this.showToast(`Compliance score: ${this.complianceScore}%`);
      } catch (e) {
        this.showToast('Compliance check failed: ' + e.message, 'fas fa-triangle-exclamation text-red');
      } finally {
        this.complianceLoading = false;
      }
    },

    // ── TinyFish agents ────────────────────────────────────────────────────────
    async refreshAgents() {
      this.agentsRunning = true;
      this.showToast('TinyFish agents dispatched…', 'fas fa-sync-alt text-blue');
      try {
        await fetch(`${API}/api/agents/run`, { method: 'POST' });
        setTimeout(() => {
          this.agentsRunning = false;
          this.showToast('Emission factors refreshed', 'fas fa-database text-accent');
        }, 4000);
      } catch {
        this.agentsRunning = false;
      }
    },
  };
}
