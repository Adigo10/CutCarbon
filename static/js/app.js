// EventCarbon Co-Pilot v2.0 — Alpine.js application logic

const API = '';  // same origin

function app() {
  return {
    // -- Nav -------------------------------------------------------------------
    activeTab: 'dashboard',
    navItems: [
      { id: 'dashboard',  label: 'Dashboard',      icon: 'fas fa-chart-line',       desc: 'Overview of your carbon footprint and savings' },
      { id: 'chat',       label: 'AI Co-Pilot',     icon: 'fas fa-robot',            desc: 'Chat with the AI to build and analyse scenarios' },
      { id: 'scenarios',  label: 'Scenarios',       icon: 'fas fa-layer-group',      desc: 'Create, edit, compare and clone emission scenarios' },
      { id: 'financial',  label: 'Financial',       icon: 'fas fa-coins',            desc: 'Carbon tax savings, incentives and ROI calculator' },
      { id: 'offsets',    label: 'Carbon Credits',  icon: 'fas fa-certificate',      desc: 'Browse offset projects, track portfolio, retire credits' },
      { id: 'compliance', label: 'Compliance',      icon: 'fas fa-shield-halved',    desc: 'GHG Protocol, ISO 20121, SBTi and regional compliance' },
    ],
    quickActions: [],

    // -- Auth ------------------------------------------------------------------
    authView: 'login',
    authEmail: '',
    authPassword: '',
    authError: '',
    authLoading: false,
    currentUser: null,
    token: localStorage.getItem('cc_token') || null,

    // -- Shared state ----------------------------------------------------------
    scenarios: [],
    selectedScenario: null,
    suggestions: [],
    toast: { show: false, message: '', icon: 'fas fa-check text-accent' },
    agentsRunning: false,

    // -- Dashboard -------------------------------------------------------------
    bestScenario: null,
    potentialSavings: null,
    complianceScore: null,
    categoryChart: null,
    comparisonChart: null,
    pathwayChart: null,
    scopeChart: null,

    emissionCategories: [
      { key: 'travel_tco2e',           label: 'Travel',        color: '#0369a1', icon: 'fa-plane' },
      { key: 'venue_energy_tco2e',     label: 'Venue Energy',  color: '#1a9e6e', icon: 'fa-bolt' },
      { key: 'accommodation_tco2e',    label: 'Accommodation', color: '#d97706', icon: 'fa-hotel' },
      { key: 'catering_tco2e',         label: 'Catering',      color: '#ea580c', icon: 'fa-utensils' },
      { key: 'materials_waste_tco2e',  label: 'Waste',         color: '#7c3aed', icon: 'fa-recycle' },
      { key: 'equipment_tco2e',        label: 'Equipment',     color: '#0891b2', icon: 'fa-gear' },
      { key: 'swag_tco2e',            label: 'Swag',          color: '#be185d', icon: 'fa-gift' },
    ],

    // -- Chat ------------------------------------------------------------------
    chatMessages: [],
    chatInput: '',
    chatLoading: false,
    chatSuggestions: [],
    chatContext: {},
    lastExtracted: null,
    sessionId: 'session-' + Math.random().toString(36).slice(2, 9),
    startSuggestions: [
      'Plan a 3-day tech conference in Singapore, 500 attendees, hybrid',
      'Estimate emissions for 200 delegates flying from Europe to London',
      'What is the carbon impact of switching our gala dinner to vegan?',
    ],

    // -- Scenarios -------------------------------------------------------------
    scenarioLoading: false,
    editingScenario: null,
    newScenario: {
      name: '',
      event_type: 'conference',
      attendees: 300,
      event_days: 2,
      location: 'Singapore',
      venue_grid: 'singapore',
      catering_type: 'mixed_buffet',
      include_alcohol: false,
      accommodation_type: 'standard_hotel',
      renewable_pct: 0,
      travel_segments: [],
      // Equipment
      stage_m2: 0,
      lighting_days: 0,
      sound_system_days: 0,
      led_screen_m2: 0,
      generator_hours: 0,
      // Swag
      tshirts: 0,
      tshirt_type: 'cotton',
      tote_bags: 0,
      lanyards: 0,
      badges: 0,
    },

    // -- Financial -------------------------------------------------------------
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
      { key: 'renewable_energy',     label: 'Renewable energy' },
      { key: 'vegetarian_menu',      label: 'Vegetarian menu' },
      { key: 'digital_materials',    label: 'Digital materials' },
      { key: 'hybrid_event',         label: 'Hybrid/virtual option' },
      { key: 'sustainable_swag',     label: 'Sustainable swag' },
      { key: 'local_seasonal',       label: 'Local/seasonal catering' },
      { key: 'led_lighting',         label: 'LED lighting upgrade' },
      { key: 'ghg_reporting',        label: 'GHG reporting' },
      { key: 'carbon_audit',         label: 'Carbon audit' },
      { key: 'sustainability_audit', label: 'Sustainability audit' },
      { key: 'carbon_offset',        label: 'Carbon offset purchase' },
      { key: 'carbon_removal',       label: 'Carbon removal purchase' },
    ],

    // -- Carbon Offsets --------------------------------------------------------
    offsetProjects: {},
    offsetRegistries: {},
    offsetMarket: {},
    offsetPurchases: [],
    offsetPortfolio: null,
    offsetRecommendations: [],
    offsetLoading: false,
    newOffset: {
      project_type: 'renewable_energy',
      registry: 'gold_standard',
      quantity_tco2e: 1.0,
      price_per_tco2e_usd: 8.50,
      vintage_year: 2025,
      notes: '',
    },

    // -- Compliance ------------------------------------------------------------
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

    // -- Init ------------------------------------------------------------------
    async init() {
      this.quickActions = [
        { icon: 'fas fa-robot', title: 'Ask the Co-Pilot', desc: 'Describe your event in plain English', handler: () => this.activeTab = 'chat' },
        { icon: 'fas fa-chart-pie', title: 'Build a Scenario', desc: 'Fill in the structured form', handler: () => this.activeTab = 'scenarios' },
        { icon: 'fas fa-coins', title: 'Calculate Savings', desc: 'See carbon tax & incentive benefits', handler: () => this.activeTab = 'financial' },
        { icon: 'fas fa-certificate', title: 'Offset Credits', desc: 'Browse and manage carbon offsets', handler: () => this.activeTab = 'offsets' },
      ];
      if (this.token) {
        try {
          // Fetch user info and scenarios in parallel
          const headers = { 'Authorization': `Bearer ${this.token}` };
          const [meRes, scenRes] = await Promise.all([
            fetch(`${API}/api/auth/me`, { headers }),
            fetch(`${API}/api/scenarios`, { headers }),
          ]);
          if (meRes.ok) {
            this.currentUser = await meRes.json();
            if (scenRes.ok) this._applyScenarios(await scenRes.json());
          } else {
            this.token = null;
            localStorage.removeItem('cc_token');
          }
        } catch (e) {
          this.token = null;
          localStorage.removeItem('cc_token');
        }
      }
    },

    // -- Auth ------------------------------------------------------------------
    authHeaders() {
      return this.token
        ? { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` }
        : { 'Content-Type': 'application/json' };
    },

    async login() {
      this.authLoading = true;
      this.authError = '';
      try {
        const res = await fetch(`${API}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: this.authEmail, password: this.authPassword }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.authError = err.detail || 'Login failed';
          return;
        }
        const data = await res.json();
        this.token = data.access_token;
        localStorage.setItem('cc_token', this.token);
        this.currentUser = data.user;  // user included in login response
        this.authEmail = '';
        this.authPassword = '';
        await this.loadScenarios();
      } catch (e) {
        this.authError = 'Network error. Please try again.';
      } finally {
        this.authLoading = false;
      }
    },

    async register() {
      this.authLoading = true;
      this.authError = '';
      try {
        const res = await fetch(`${API}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: this.authEmail, password: this.authPassword }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.authError = err.detail || 'Registration failed';
          return;
        }
        const data = await res.json();
        this.token = data.access_token;
        localStorage.setItem('cc_token', this.token);
        this.currentUser = data.user;  // user included in register response
        this.authEmail = '';
        this.authPassword = '';
        // new account has no scenarios yet
      } catch (e) {
        this.authError = 'Network error. Please try again.';
      } finally {
        this.authLoading = false;
      }
    },

    logout() {
      this.token = null;
      this.currentUser = null;
      localStorage.removeItem('cc_token');
      this.scenarios = [];
      this.selectedScenario = null;
      this.bestScenario = null;
      this.potentialSavings = null;
      this.complianceScore = null;
    },

    // -- Toast -----------------------------------------------------------------
    showToast(message, icon = 'fas fa-check text-accent') {
      this.toast = { show: true, message, icon };
      setTimeout(() => this.toast.show = false, 3500);
    },

    // -- Scenarios -------------------------------------------------------------
    _applyScenarios(list) {
      this.scenarios = list;
      if (list.length > 0) {
        this.bestScenario = [...list].sort((a, b) => a.emissions.total_tco2e - b.emissions.total_tco2e)[0];
        if (!this.selectedScenario) this.selectedScenario = list[0];
        this.potentialSavings = Math.round(this.bestScenario.emissions.total_tco2e * 0.3 * 25 * 0.74);
        // Use setTimeout(0) after $nextTick so browser reflows before Chart.js measures canvas dimensions
        this.$nextTick(() => setTimeout(() => this.drawCharts(), 0));
      }
    },

    async loadScenarios() {
      try {
        const res = await fetch(`${API}/api/scenarios`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        if (res.ok) this._applyScenarios(await res.json());
      } catch (e) {
        console.error(e);
      }
    },

    async calculateScenario() {
      this.scenarioLoading = true;
      try {
        const payload = this._buildScenarioPayload();
        const isEdit = !!this.editingScenario;
        const url = isEdit
          ? `${API}/api/scenarios/${this.editingScenario.scenario_id}`
          : `${API}/api/scenarios`;
        const method = isEdit ? 'PUT' : 'POST';

        const res = await fetch(url, {
          method,
          headers: this.authHeaders(),
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(await res.text());
        const scenario = await res.json();

        if (isEdit) {
          const idx = this.scenarios.findIndex(s => s.scenario_id === this.editingScenario.scenario_id);
          if (idx >= 0) this.scenarios[idx] = scenario;
          this.editingScenario = null;
        } else {
          this.scenarios.unshift(scenario);
        }

        this.selectedScenario = scenario;
        this.bestScenario = [...this.scenarios].sort(
          (a, b) => a.emissions.total_tco2e - b.emissions.total_tco2e
        )[0];
        this.newScenario.name = '';
        this.newScenario.travel_segments = [];
        this.showToast(`Scenario "${scenario.name}" ${isEdit ? 'updated' : 'calculated'}: ${scenario.emissions.total_tco2e.toFixed(2)} tCO2e`);
        this.$nextTick(() => setTimeout(() => this.drawCharts(), 0));
        this.complianceScore = Math.round(50 + (scenario.emissions.per_attendee_tco2e < 0.5 ? 30 : 0));
      } catch (e) {
        this.showToast('Error: ' + e.message, 'fas fa-triangle-exclamation text-red');
      } finally {
        this.scenarioLoading = false;
      }
    },

    editScenario(s) {
      this.editingScenario = s;
      const p = s.input_payload || {};
      this.newScenario.name = s.name;
      this.newScenario.event_type = s.event_type || 'conference';
      this.newScenario.attendees = s.attendees;
      this.newScenario.event_days = s.event_days;
      this.newScenario.location = p.location || 'Singapore';
      this.newScenario.venue_grid = p.venue_energy?.grid_region || 'singapore';
      this.newScenario.renewable_pct = p.venue_energy?.renewable_pct || 0;
      this.newScenario.catering_type = p.catering?.catering_type || 'mixed_buffet';
      this.newScenario.include_alcohol = p.catering?.include_alcohol || false;
      this.newScenario.accommodation_type = p.accommodation?.accommodation_type || 'standard_hotel';
      this.newScenario.travel_segments = p.travel_segments || [];
      this.newScenario.stage_m2 = p.equipment?.stage_m2 || 0;
      this.newScenario.lighting_days = p.equipment?.lighting_days || 0;
      this.newScenario.sound_system_days = p.equipment?.sound_system_days || 0;
      this.newScenario.led_screen_m2 = p.equipment?.led_screen_m2 || 0;
      this.newScenario.generator_hours = p.equipment?.generator_hours || 0;
      this.newScenario.tshirts = p.swag?.tshirts || 0;
      this.newScenario.tshirt_type = p.swag?.tshirt_type || 'cotton';
      this.newScenario.tote_bags = p.swag?.tote_bags || 0;
      this.newScenario.lanyards = p.swag?.lanyards || 0;
      this.newScenario.badges = p.swag?.badges || 0;
      this.activeTab = 'scenarios';
      this.showToast('Editing: ' + s.name);
    },

    cancelEdit() {
      this.editingScenario = null;
      this.newScenario.name = '';
    },

    _buildScenarioPayload() {
      const ns = this.newScenario;
      const payload = {
        name: ns.name || 'Scenario ' + (this.scenarios.length + 1),
        event_name: ns.location + ' Event',
        event_type: ns.event_type,
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
          include_alcohol: ns.include_alcohol,
        },
        accommodation: {
          accommodation_type: ns.accommodation_type,
          room_nights: Math.ceil(ns.attendees * 0.8 / 1.5) * ns.event_days,
        },
      };

      if (ns.travel_segments && ns.travel_segments.length > 0) {
        payload.travel_segments = ns.travel_segments.map(seg => ({
          mode: seg.mode,
          travel_class: seg.travel_class || 'economy',
          attendees: seg.attendees || 50,
          distance_km: seg.distance_km || 500,
          label: seg.mode,
        }));
      }

      // Equipment (only if any values set)
      if (ns.stage_m2 || ns.lighting_days || ns.sound_system_days || ns.led_screen_m2 || ns.generator_hours) {
        payload.equipment = {
          stage_m2: ns.stage_m2 || 0,
          lighting_days: ns.lighting_days || 0,
          sound_system_days: ns.sound_system_days || 0,
          led_screen_m2: ns.led_screen_m2 || 0,
          projectors: 0,
          generator_hours: ns.generator_hours || 0,
          freight_tonne_km: 0,
        };
      }

      // Swag (only if any values set)
      if (ns.tshirts || ns.tote_bags || ns.lanyards || ns.badges) {
        payload.swag = {
          tshirts: ns.tshirts || 0,
          tshirt_type: ns.tshirt_type || 'cotton',
          tote_bags: ns.tote_bags || 0,
          lanyards: ns.lanyards || 0,
          badges: ns.badges || 0,
          badge_type: 'plastic',
          notebooks: 0,
          water_bottles: 0,
        };
      }

      return payload;
    },

    async cloneScenario(scenario) {
      const name = prompt('Name for cloned scenario:', 'Copy of ' + scenario.name);
      if (!name) return;
      try {
        const res = await fetch(`${API}/api/scenarios/${scenario.scenario_id}/clone?name=${encodeURIComponent(name)}`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        const cloned = await res.json();
        this.scenarios.unshift(cloned);
        this.showToast('Scenario cloned: ' + name);
        this.$nextTick(() => setTimeout(() => this.drawCharts(), 0));
      } catch (e) {
        this.showToast('Clone failed', 'fas fa-triangle-exclamation text-red');
      }
    },

    async deleteScenario(id) {
      if (!confirm('Delete this scenario?')) return;
      await fetch(`${API}/api/scenarios/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${this.token}` },
      });
      this.scenarios = this.scenarios.filter(s => s.scenario_id !== id);
      if (this.selectedScenario?.scenario_id === id) this.selectedScenario = this.scenarios[0] || null;
      this.suggestions = [];
      this.showToast('Scenario deleted');
      this.$nextTick(() => setTimeout(() => this.drawCharts(), 0));
    },

    async exportScenario(s) {
      try {
        const res = await fetch(`${API}/api/scenarios/${s.scenario_id}/export`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cutcarbon_${s.scenario_id}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('Report exported');
      } catch (e) {
        this.showToast('Export failed', 'fas fa-triangle-exclamation text-red');
      }
    },

    selectScenario(s) {
      this.selectedScenario = s;
      this.suggestions = [];
      this.finCalc.baseline = s.emissions.total_tco2e;
      this.complianceInput.total_tco2e = s.emissions.total_tco2e;
      this.complianceInput.attendees = s.attendees;
      this.complianceInput.event_days = s.event_days;
      this.$nextTick(() => setTimeout(() => this.drawCharts(), 0));
    },

    async getSuggestions(scenario) {
      try {
        const res = await fetch(`${API}/api/scenarios/${scenario.scenario_id}/suggestions?target_pct=30`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        this.suggestions = await res.json();
        this.showToast('Reduction suggestions loaded');
      } catch (e) {
        this.showToast('Failed to load suggestions', 'fas fa-triangle-exclamation text-red');
      }
    },

    addTravelSegment() {
      this.newScenario.travel_segments.push({
        mode: 'long_haul_flight',
        travel_class: 'economy',
        attendees: 100,
        distance_km: 2000,
      });
    },

    // -- Charts ----------------------------------------------------------------
    drawCharts() {
      this.drawCategoryChart();
      this.drawComparisonChart();
      if (this.selectedScenario) {
        this.drawPathwayChart();
        this.drawScopeChart();
      }
    },

    drawCategoryChart() {
      const s = this.selectedScenario;
      if (!s) return;
      const ctx = document.getElementById('categoryChart');
      if (!ctx) return;
      if (this.categoryChart) this.categoryChart.destroy();

      const cats = this.emissionCategories.filter(c => (s.emissions[c.key] || 0) > 0);
      const labels = cats.map(c => c.label);
      const data = cats.map(c => (s.emissions[c.key] || 0) * 1000);
      const colors = cats.map(c => c.color);

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
              labels: { color: '#6b7280', font: { size: 11 }, boxWidth: 12 },
            },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.label}: ${(ctx.raw / 1000).toFixed(3)} tCO2e (${((ctx.raw / data.reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%)`,
              },
            },
          },
        },
      });
    },

    drawScopeChart() {
      const s = this.selectedScenario;
      if (!s?.emissions?.scopes) return;
      const ctx = document.getElementById('scopeChart');
      if (!ctx) return;
      if (this.scopeChart) this.scopeChart.destroy();

      const scopes = s.emissions.scopes;
      const labels = ['Scope 1 (Direct)', 'Scope 2 (Energy)', 'Scope 3 (Indirect)'];
      const data = [scopes.scope1_tco2e || 0, scopes.scope2_tco2e || 0, scopes.scope3_tco2e || 0];
      const colors = ['#dc2626', '#d97706', '#0369a1'];

      this.scopeChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{ data, backgroundColor: colors, borderRadius: 6, barThickness: 40 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          scales: {
            x: { ticks: { color: '#6b7280', callback: v => v + ' t' }, grid: { color: '#e5e7eb' } },
            y: { ticks: { color: '#6b7280', font: { size: 11 } }, grid: { display: false } },
          },
          plugins: { legend: { display: false } },
        },
      });
    },

    drawComparisonChart() {
      const ctx = document.getElementById('comparisonChart');
      if (!ctx || this.scenarios.length === 0) return;
      if (this.comparisonChart) this.comparisonChart.destroy();

      const cats = this.emissionCategories;
      const labels = this.scenarios.slice(0, 6).map(s => s.name);

      const datasets = cats.map((cat) => ({
        label: cat.label,
        data: this.scenarios.slice(0, 6).map(s => (s.emissions[cat.key] || 0) * 1000),
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
            x: { stacked: true, ticks: { color: '#6b7280', font: { size: 10 } }, grid: { color: '#e5e7eb' } },
            y: {
              stacked: true,
              ticks: { color: '#6b7280', font: { size: 10 }, callback: v => v.toFixed(0) + ' kg' },
              grid: { color: '#e5e7eb' },
            },
          },
          plugins: {
            legend: { labels: { color: '#6b7280', font: { size: 10 }, boxWidth: 10 } },
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
      const pathway = years.map(y => +(base * Math.max(0, 1 - (y - 2024) / 26)).toFixed(3));
      const sbti = years.map(y => +(base * Math.max(0, 1 - (y - 2024) / 26 * 1.3)).toFixed(3));

      this.pathwayChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: years,
          datasets: [
            {
              label: 'Your pathway',
              data: pathway,
              borderColor: '#1a9e6e',
              backgroundColor: 'rgba(26,158,110,0.08)',
              fill: true,
              tension: 0.4,
              pointBackgroundColor: '#1a9e6e',
            },
            {
              label: 'SBTi 1.5C budget',
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
            x: { ticks: { color: '#6b7280' }, grid: { color: '#e5e7eb' } },
            y: {
              ticks: { color: '#6b7280', callback: v => v + ' t' },
              grid: { color: '#e5e7eb' },
            },
          },
          plugins: {
            legend: { labels: { color: '#6b7280', font: { size: 11 } } },
          },
        },
      });
    },

    // -- Chat ------------------------------------------------------------------
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
          headers: this.authHeaders(),
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
      return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code style="background:var(--surface-2);padding:1px 5px;border-radius:4px;font-family:monospace;color:var(--accent)">$1</code>')
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

    // -- Financial -------------------------------------------------------------
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

    // -- Carbon Offsets --------------------------------------------------------
    async loadOffsetData() {
      try {
        const [projRes, regRes, mktRes, purRes, portRes] = await Promise.all([
          fetch(`${API}/api/offsets/projects`),
          fetch(`${API}/api/offsets/registries`),
          fetch(`${API}/api/offsets/market`),
          fetch(`${API}/api/offsets`, { headers: { 'Authorization': `Bearer ${this.token}` } }),
          fetch(`${API}/api/offsets/portfolio`, { headers: { 'Authorization': `Bearer ${this.token}` } }),
        ]);
        this.offsetProjects = await projRes.json();
        this.offsetRegistries = await regRes.json();
        this.offsetMarket = await mktRes.json();
        this.offsetPurchases = await purRes.json();
        this.offsetPortfolio = await portRes.json();
      } catch (e) {
        console.error('Failed to load offset data:', e);
      }
    },

    async createOffsetPurchase() {
      this.offsetLoading = true;
      try {
        const res = await fetch(`${API}/api/offsets`, {
          method: 'POST',
          headers: this.authHeaders(),
          body: JSON.stringify({
            scenario_id: this.selectedScenario?.scenario_id || null,
            project_type: this.newOffset.project_type,
            registry: this.newOffset.registry,
            quantity_tco2e: this.newOffset.quantity_tco2e,
            price_per_tco2e_usd: this.newOffset.price_per_tco2e_usd,
            vintage_year: this.newOffset.vintage_year,
            notes: this.newOffset.notes,
          }),
        });
        if (!res.ok) throw new Error(await res.text());
        const purchase = await res.json();
        this.offsetPurchases.unshift(purchase);
        await this.refreshPortfolio();
        this.showToast(`Purchased ${purchase.quantity_tco2e} tCO2e offset credits`);
      } catch (e) {
        this.showToast('Purchase failed: ' + e.message, 'fas fa-triangle-exclamation text-red');
      } finally {
        this.offsetLoading = false;
      }
    },

    async retireOffset(id) {
      try {
        const res = await fetch(`${API}/api/offsets/${id}/retire`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        if (!res.ok) throw new Error(await res.text());
        const idx = this.offsetPurchases.findIndex(p => p.id === id);
        if (idx >= 0) this.offsetPurchases[idx].status = 'retired';
        await this.refreshPortfolio();
        this.showToast('Credit retired successfully');
      } catch (e) {
        this.showToast('Retire failed: ' + e.message, 'fas fa-triangle-exclamation text-red');
      }
    },

    async cancelOffset(id) {
      if (!confirm('Cancel this offset purchase?')) return;
      try {
        await fetch(`${API}/api/offsets/${id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        const idx = this.offsetPurchases.findIndex(p => p.id === id);
        if (idx >= 0) this.offsetPurchases[idx].status = 'cancelled';
        await this.refreshPortfolio();
        this.showToast('Purchase cancelled');
      } catch (e) {
        this.showToast('Cancel failed', 'fas fa-triangle-exclamation text-red');
      }
    },

    async loadOffsetRecommendations() {
      if (!this.selectedScenario) return;
      try {
        const res = await fetch(`${API}/api/offsets/recommend/${this.selectedScenario.scenario_id}`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        this.offsetRecommendations = await res.json();
      } catch (e) {
        console.error(e);
      }
    },

    async refreshPortfolio() {
      try {
        const res = await fetch(`${API}/api/offsets/portfolio`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        this.offsetPortfolio = await res.json();
      } catch (e) { /* ignore */ }
    },

    updateOffsetPrice() {
      const proj = this.offsetProjects[this.newOffset.project_type];
      if (proj) this.newOffset.price_per_tco2e_usd = proj.avg_price_usd;
    },

    // -- Compliance ------------------------------------------------------------
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

    // -- TinyFish agents -------------------------------------------------------
    async refreshAgents() {
      this.agentsRunning = true;
      this.showToast('TinyFish agents dispatched...', 'fas fa-sync-alt text-blue');
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
