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
      { id: 'data',       label: 'Data & Exports',  icon: 'fas fa-file-export',      desc: 'Download data as Excel or JSON, view agent run history' },
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

    // -- Data & Exports --------------------------------------------------------
    agentStatus: [],
    agentHistory: [],

    // -- Dashboard -------------------------------------------------------------
    bestScenario: null,
    potentialSavings: null,
    complianceScore: null,
    categoryChart: null,
    comparisonChart: null,
    pathwayChart: null,
    scopeChart: null,
    intensityTrendChart: null,
    opportunityChart: null,
    factorsChart: null,
    dashboardRenderTimer: null,
    dashboardStabilizeTimer: null,
    dashboardChartError: '',
    dashboardRenderAttempts: 0,

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
      linked_scenario_id: null,
      linked_scenario_name: null,
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
      // Initialise Mermaid with dark-friendly theme
      if (typeof mermaid !== 'undefined') {
        mermaid.initialize({ startOnLoad: false, theme: 'neutral', fontFamily: 'Inter, system-ui, sans-serif' });
      }

      this.quickActions = [
        { icon: 'fas fa-robot', title: 'Ask the Co-Pilot', desc: 'Describe your event in plain English', handler: () => this.activeTab = 'chat' },
        { icon: 'fas fa-chart-pie', title: 'Build a Scenario', desc: 'Fill in the structured form', handler: () => this.activeTab = 'scenarios' },
        { icon: 'fas fa-coins', title: 'Calculate Savings', desc: 'See carbon tax & incentive benefits', handler: () => this.activeTab = 'financial' },
        { icon: 'fas fa-certificate', title: 'Offset Credits', desc: 'Browse and manage carbon offsets', handler: () => this.activeTab = 'offsets' },
      ];

      // Redraw charts when viewport changes to keep canvases visible and sized correctly.
      window.addEventListener('resize', () => {
        if (this.activeTab === 'dashboard') this.scheduleDashboardRender();
      });

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

    switchTab(tabId) {
      this.activeTab = tabId;
      if (tabId === 'offsets') this.loadOffsetData();
      if (tabId === 'data') this.loadAgentStatus();
      if (tabId === 'dashboard') this.scheduleDashboardRender();
    },

    scheduleDashboardRender() {
      if (this.dashboardRenderTimer) {
        clearTimeout(this.dashboardRenderTimer);
        this.dashboardRenderTimer = null;
      }
      if (this.dashboardStabilizeTimer) {
        clearTimeout(this.dashboardStabilizeTimer);
        this.dashboardStabilizeTimer = null;
      }
      // Increment version on the DOM element (non-reactive) so any in-progress retry loops
      // from a previous render cycle abort without triggering Alpine's x-effect again.
      const el = this.$el;
      const version = (el._chartRenderVersion = (el._chartRenderVersion || 0) + 1);

      this.$nextTick(() => {
        // Wait for x-show/x-transition layout before Chart.js measures canvas dimensions.
        this.dashboardRenderTimer = setTimeout(() => {
          if (this.activeTab !== 'dashboard' || el._chartRenderVersion !== version) return;
          if (!this.selectedScenario && this.scenarios.length > 0) this.selectedScenario = this.scenarios[0];

          // Wait for Alpine to process the selectedScenario reactive update (removes display:none
          // from x-show="selectedScenario" canvas containers) before checking canvas dimensions.
          this.$nextTick(() => {
            if (el._chartRenderVersion !== version) return;
            this.dashboardRenderAttempts = 0;
            this.drawChartsWhenReady(true, false, version, el);
            this.renderFlowchart();

            // A second delayed pass avoids zero-size canvases during transitions.
            // reportErrors=true so that persistent failures are surfaced after this final attempt.
            this.dashboardStabilizeTimer = setTimeout(() => {
              if (this.activeTab !== 'dashboard' || el._chartRenderVersion !== version) return;
              this.drawChartsWhenReady(false, true, version, el);
            }, 420);
          });
        }, 120);
      });
    },

    drawChartsWhenReady(resetError = true, reportErrors = false, version = 0, el = null) {
      if (version && el && el._chartRenderVersion !== version) return;

      const categoryCanvas = document.getElementById('categoryChart');
      const comparisonCanvas = document.getElementById('comparisonChart');
      const hasScenarioCanvas = !this.selectedScenario || (
        categoryCanvas && categoryCanvas.clientWidth > 0 && categoryCanvas.clientHeight > 0
      );
      // If there are no scenarios the comparison canvas stays display:none — treat as ready (nothing to draw).
      const hasComparisonCanvas = this.scenarios.length === 0 || !comparisonCanvas || (
        comparisonCanvas.clientWidth > 0 && comparisonCanvas.clientHeight > 0
      );

      if (hasScenarioCanvas && hasComparisonCanvas) {
        this.drawCharts(resetError, reportErrors);
        return;
      }

      if (this.dashboardRenderAttempts >= 8) {
        this.drawCharts(resetError, reportErrors);
        return;
      }

      this.dashboardRenderAttempts += 1;
      const attempt = this.dashboardRenderAttempts;
      setTimeout(() => {
        if (this.activeTab !== 'dashboard') return;
        if (version && el && el._chartRenderVersion !== version) return;
        this.drawChartsWhenReady(resetError && attempt === 1, reportErrors, version, el);
      }, 140);
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
      const currentSelectedId = this.selectedScenario?.scenario_id || null;
      this.scenarios = list;
      if (list.length > 0) {
        this.bestScenario = [...list].sort((a, b) => a.emissions.total_tco2e - b.emissions.total_tco2e)[0];
        this.selectedScenario = currentSelectedId
          ? (list.find(s => s.scenario_id === currentSelectedId) || list[0])
          : list[0];
        this.potentialSavings = Math.round(this.bestScenario.emissions.total_tco2e * 0.3 * 25 * 0.74);
        if (this.selectedScenario) this.loadScenarioIntoFinCalc(this.selectedScenario);
        this.scheduleDashboardRender();
      } else {
        this.selectedScenario = null;
        this.bestScenario = null;
        this.potentialSavings = null;
        this.scheduleDashboardRender();
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
        this.scheduleDashboardRender();
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
        this.scheduleDashboardRender();
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
      this.scheduleDashboardRender();
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
      this.loadScenarioIntoFinCalc(s);
      this.complianceInput.total_tco2e = s.emissions.total_tco2e;
      this.complianceInput.attendees = s.attendees;
      this.complianceInput.event_days = s.event_days;
      this.scheduleDashboardRender();
    },

    loadScenarioIntoFinCalc(s) {
      const p = s.input_payload || {};
      const attendees = s.attendees || 0;
      const days = s.event_days || 1;
      const renewablePct = p.venue_energy?.renewable_pct || 0;

      // Proxy kWh formula mirrors the backend emissions engine
      const proxyKwh = attendees * 2.0 * days * 30;
      const kwhSavable = Math.round(proxyKwh * (1 - renewablePct / 100));

      const cateringType = p.catering?.catering_type || 'mixed_buffet';
      const switchPct = { meat_heavy: 0.60, seafood_heavy: 0.40, mixed_buffet: 0.35,
                          vegetarian: 0.0, vegan: 0.0 }[cateringType] || 0.30;
      const totalMeals = attendees * days * 2;
      const mealSwitches = Math.round(totalMeals * switchPct);

      this.finCalc.baseline = s.emissions.total_tco2e;
      this.finCalc.energy_kwh = kwhSavable;
      this.finCalc.meal_switches = mealSwitches;
      this.finCalc.linked_scenario_id = s.scenario_id;
      this.finCalc.linked_scenario_name = s.name;
      this.finResult = null;
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

    topEmissionSource(scenario) {
      if (!scenario?.emissions) return { label: 'N/A', key: null, value: 0 };
      const top = this.emissionCategories
        .map(c => ({ key: c.key, label: c.label, value: scenario.emissions[c.key] || 0 }))
        .sort((a, b) => b.value - a.value)[0];
      return top || { label: 'N/A', key: null, value: 0 };
    },

    scenarioRank(scenario) {
      if (!scenario || this.scenarios.length === 0) return 0;
      const sorted = [...this.scenarios].sort((a, b) => (a.emissions?.total_tco2e || 0) - (b.emissions?.total_tco2e || 0));
      return Math.max(1, sorted.findIndex(s => s.scenario_id === scenario.scenario_id) + 1);
    },

    scenarioGapToBest(scenario) {
      if (!scenario || !this.bestScenario) return 0;
      const best = this.bestScenario.emissions?.total_tco2e || 0;
      const current = scenario.emissions?.total_tco2e || 0;
      if (best <= 0 || current <= 0) return 0;
      return ((current - best) / current) * 100;
    },

    emissionIntensityBand(scenario) {
      const kg = (scenario?.emissions?.per_attendee_tco2e || 0) * 1000;
      if (kg === 0) return 'No intensity data';
      if (kg < 90) return 'Low-intensity profile';
      if (kg < 180) return 'Moderate-intensity profile';
      return 'High-intensity profile';
    },

    estimatedReductionOpportunity(scenario) {
      if (!scenario?.emissions) return 0;
      const reductionFactors = {
        travel_tco2e: 0.22,
        venue_energy_tco2e: 0.45,
        accommodation_tco2e: 0.18,
        catering_tco2e: 0.35,
        materials_waste_tco2e: 0.40,
        equipment_tco2e: 0.25,
        swag_tco2e: 0.50,
      };

      return this.emissionCategories.reduce((sum, cat) => {
        const value = scenario.emissions[cat.key] || 0;
        const factor = reductionFactors[cat.key] || 0;
        return sum + value * factor;
      }, 0);
    },

    // -- Charts ----------------------------------------------------------------
    drawCharts(resetError = true, reportErrors = true) {
      if (resetError) this.dashboardChartError = '';

      if (typeof Chart === 'undefined') {
        if (reportErrors) this.dashboardChartError = 'Chart.js failed to load. Check internet/CDN access and refresh.';
        return;
      }

      try {
        this.drawCategoryChart();
        this.drawComparisonChart();
        if (this.selectedScenario) {
          this.drawPathwayChart();
          this.drawScopeChart();
          this.drawOpportunityChart();
          this.drawFactorsChart();
        }
        this.drawIntensityTrendChart();
        // Successful render — always clear any stale error
        this.dashboardChartError = '';
      } catch (err) {
        if (reportErrors) {
          const msg = err && err.message ? err.message : 'Unknown chart rendering error';
          this.dashboardChartError = `Dashboard charts failed to render: ${msg}`;
        }
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

    drawIntensityTrendChart() {
      const ctx = document.getElementById('intensityTrendChart');
      if (!ctx || this.scenarios.length === 0) return;
      if (this.intensityTrendChart) this.intensityTrendChart.destroy();

      const rows = [...this.scenarios]
        .sort((a, b) => {
          const aKey = (a.created_at || '').toString();
          const bKey = (b.created_at || '').toString();
          if (aKey && bKey) return aKey.localeCompare(bKey);
          return (a.scenario_id || 0) - (b.scenario_id || 0);
        })
        .slice(-10);

      const labels = rows.map(s => s.name.length > 16 ? `${s.name.slice(0, 16)}...` : s.name);
      const totals = rows.map(s => s.emissions?.total_tco2e || 0);
      const intensityKg = rows.map(s => (s.emissions?.per_attendee_tco2e || 0) * 1000);

      this.intensityTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Total tCO2e',
              data: totals,
              borderColor: '#1a9e6e',
              backgroundColor: 'rgba(26,158,110,0.18)',
              fill: true,
              tension: 0.28,
              pointRadius: 3,
              yAxisID: 'yTotal',
            },
            {
              label: 'kg CO2e / attendee',
              data: intensityKg,
              borderColor: '#0369a1',
              backgroundColor: 'transparent',
              borderDash: [6, 4],
              tension: 0.28,
              pointRadius: 2,
              yAxisID: 'yIntensity',
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            x: { ticks: { color: '#6b7280', font: { size: 10 } }, grid: { color: '#e5e7eb' } },
            yTotal: {
              position: 'left',
              ticks: { color: '#1a9e6e', callback: v => `${v.toFixed(1)} t` },
              grid: { color: '#e5e7eb' },
            },
            yIntensity: {
              position: 'right',
              ticks: { color: '#0369a1', callback: v => `${v.toFixed(0)} kg` },
              grid: { drawOnChartArea: false },
            },
          },
          plugins: {
            legend: { labels: { color: '#6b7280', boxWidth: 10, font: { size: 10 } } },
          },
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

    drawOpportunityChart() {
      const s = this.selectedScenario;
      if (!s?.emissions) return;

      const ctx = document.getElementById('opportunityChart');
      if (!ctx) return;
      if (this.opportunityChart) this.opportunityChart.destroy();

      const reductionFactors = {
        travel_tco2e: 0.22,
        venue_energy_tco2e: 0.45,
        accommodation_tco2e: 0.18,
        catering_tco2e: 0.35,
        materials_waste_tco2e: 0.40,
        equipment_tco2e: 0.25,
        swag_tco2e: 0.50,
      };

      const rows = this.emissionCategories
        .map(cat => {
          const base = s.emissions[cat.key] || 0;
          return {
            label: cat.label,
            value: +(base * (reductionFactors[cat.key] || 0)).toFixed(4),
            color: cat.color,
          };
        })
        .filter(r => r.value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, 6);

      this.opportunityChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: rows.map(r => r.label),
          datasets: [{
            label: 'Potential reduction (tCO2e)',
            data: rows.map(r => r.value),
            backgroundColor: rows.map(r => `${r.color}cc`),
            borderColor: rows.map(r => r.color),
            borderWidth: 1,
            borderRadius: 6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          scales: {
            x: { ticks: { color: '#6b7280', callback: v => `${v} t` }, grid: { color: '#e5e7eb' } },
            y: { ticks: { color: '#6b7280', font: { size: 11 } }, grid: { display: false } },
          },
          plugins: {
            legend: { display: false },
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

    drawFactorsChart() {
      if (this.factorsChart) {
        this.factorsChart.destroy();
        this.factorsChart = null;
      }
      const s = this.selectedScenario;
      const snap = s?.factors_snapshot;
      if (!snap || !Object.keys(snap).length) return;
      const ctx = document.getElementById('factorsChart');
      if (!ctx) return;

      const rows = [
        { label: 'Long-haul flight', unit: 'kg/pkm', value: snap.travel_long_haul_economy_kg_per_pkm, color: '#0ea5e9' },
        { label: 'Short-haul flight', unit: 'kg/pkm', value: snap.travel_short_haul_economy_kg_per_pkm, color: '#38bdf8' },
        { label: 'Car (petrol)', unit: 'kg/pkm', value: snap.travel_car_petrol_kg_per_pkm, color: '#f59e0b' },
        { label: `Grid (${(snap.venue_grid_region || 'global').replace('_', ' ')})`, unit: 'kg/kWh', value: snap.venue_grid_kg_per_kwh, color: '#eab308' },
        { label: `Catering (${(snap.catering_type || 'mixed').replace(/_/g, ' ')})`, unit: 'kg/meal', value: snap.catering_kg_per_meal, color: '#22c55e' },
        { label: `Accommodation`, unit: 'kg/room-night÷10', value: (snap.accommodation_kg_per_room_night || 0) / 10, color: '#8b5cf6' },
        { label: 'Waste (landfill)', unit: 'kg/kg', value: snap.waste_landfill_kg_per_kg, color: '#6b7280' },
      ].filter(r => r.value > 0);

      const version = snap.ef_version ? ` · EF v${snap.ef_version}` : '';
      this.factorsChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: rows.map(r => `${r.label} (${r.unit})`),
          datasets: [{
            label: 'Factor value',
            data: rows.map(r => r.value),
            backgroundColor: rows.map(r => `${r.color}cc`),
            borderColor: rows.map(r => r.color),
            borderWidth: 1,
            borderRadius: 5,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          scales: {
            x: {
              ticks: { color: '#6b7280', font: { size: 10 }, callback: v => v.toFixed(3) },
              grid: { color: '#e5e7eb' },
              title: { display: true, text: `kg CO2e per unit${version}`, color: '#9ca3af', font: { size: 10 } },
            },
            y: { ticks: { color: '#6b7280', font: { size: 10 } }, grid: { display: false } },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.raw.toFixed(4)} kg CO2e / ${rows[ctx.dataIndex]?.unit || 'unit'}`,
              },
            },
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
      this.showToast('Refreshing factors and recalculating scenarios...', 'fas fa-sync-alt text-blue');
      const previouslySelectedId = this.selectedScenario?.scenario_id || null;
      let agentOk = false;

      // Step 1: refresh global emission factors via TinyFish (non-fatal if it fails)
      try {
        const runRes = await fetch(`${API}/api/agents/run/sync?force=true`);
        agentOk = runRes.ok;
      } catch (_) {
        // TinyFish unavailable — proceed to recalculate with existing factors
      }

      // Step 2: recalculate all scenarios (always, regardless of TinyFish result)
      if (this.token) {
        try {
          const recalcRes = await fetch(`${API}/api/scenarios/recalculate/all`, {
            method: 'POST',
            headers: this.authHeaders(),
          });
          if (!recalcRes.ok) throw new Error('Recalculate request failed');

          const recalc = await recalcRes.json();
          if (Array.isArray(recalc.scenarios)) {
            this._applyScenarios(recalc.scenarios);
            if (previouslySelectedId) {
              const restored = this.scenarios.find(s => s.scenario_id === previouslySelectedId);
              if (restored) this.selectScenario(restored);
            }
          }

          const agentNote = agentOk ? '' : ' (factors unchanged — agent offline)';
          if (recalc.failed_count > 0) {
            this.showToast(
              `${recalc.updated_count} scenarios recalculated, ${recalc.failed_count} failed${agentNote}`,
              'fas fa-triangle-exclamation text-gold'
            );
          } else {
            this.showToast(`${recalc.updated_count} scenario(s) recalculated${agentNote}`, 'fas fa-database text-accent');
          }
        } catch (e) {
          this.showToast(`Recalculate failed: ${e.message}`, 'fas fa-triangle-exclamation text-red');
        }
      } else {
        this.showToast(
          agentOk ? 'Emission factors refreshed' : 'Agent offline — factors unchanged',
          'fas fa-database text-accent'
        );
      }

      try { await this.loadAgentStatus(); } catch (_) {}
      this.agentsRunning = false;
    },

    async refreshAgentsForceful() {
      this.agentsRunning = true;
      this.showToast('Force re-fetching all agents...', 'fas fa-bolt text-gold');
      try {
        await fetch(`${API}/api/agents/run?force=true`, { method: 'POST' });
        setTimeout(async () => {
          this.agentsRunning = false;
          await this.loadAgentStatus();
          this.showToast('Force refresh dispatched', 'fas fa-bolt text-gold');
        }, 4000);
      } catch {
        this.agentsRunning = false;
      }
    },

    // -- Data & Exports --------------------------------------------------------
    async loadAgentStatus() {
      try {
        const res = await fetch(`${API}/api/agents/status`);
        if (res.ok) this.agentStatus = await res.json();
      } catch (e) {
        console.error('Failed to load agent status:', e);
      }
    },

    async loadAgentHistory() {
      try {
        const res = await fetch(`${API}/api/agents/history?limit=50`);
        if (res.ok) this.agentHistory = await res.json();
      } catch (e) {
        console.error('Failed to load agent history:', e);
      }
    },

    downloadFile(url, filename) {
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
    },

    downloadFileAuth(url, filename) {
      // For auth-protected endpoints, fetch with bearer token then trigger download
      fetch(url, { headers: { 'Authorization': `Bearer ${this.token}` } })
        .then(r => r.blob())
        .then(blob => {
          const objUrl = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = objUrl;
          a.download = filename;
          a.click();
          URL.revokeObjectURL(objUrl);
        })
        .catch(() => this.showToast('Download failed', 'fas fa-triangle-exclamation text-red'));
    },

    downloadScenarioReport() {
      if (!this.selectedScenario) {
        this.showToast('Select a scenario first', 'fas fa-triangle-exclamation text-gold');
        return;
      }
      this.downloadFile(
        `/api/exports/scenarios/${this.selectedScenario.scenario_id}.xlsx`,
        `report_${this.selectedScenario.scenario_id}.xlsx`
      );
    },

    // -- Mermaid flowchart -----------------------------------------------------
    async renderFlowchart() {
      const s = this.selectedScenario;
      if (!s) return;

      const em = s.emissions;
      const total = em.total_tco2e || 0.001;
      const fmt = v => (v || 0).toFixed(3) + ' t';

      const categories = [
        { key: 'travel_tco2e',          label: 'Travel',        id: 'TR', scope: 3, color: '#0369a1' },
        { key: 'venue_energy_tco2e',     label: 'Venue Energy',  id: 'VE', scope: 2, color: '#1a9e6e' },
        { key: 'accommodation_tco2e',    label: 'Accommodation', id: 'AC', scope: 3, color: '#d97706' },
        { key: 'catering_tco2e',         label: 'Catering',      id: 'CA', scope: 3, color: '#ea580c' },
        { key: 'materials_waste_tco2e',  label: 'Waste',         id: 'WA', scope: 3, color: '#7c3aed' },
      ].filter(c => (em[c.key] || 0) > 0);

      const scopes = s.emissions.scopes || {};
      const s1 = (scopes.scope1_tco2e || 0).toFixed(3);
      const s2 = (scopes.scope2_tco2e || 0).toFixed(3);
      const s3 = (scopes.scope3_tco2e || 0).toFixed(3);

      let diagram = `flowchart TD\n`;
      diagram += `  EVT["🏢 ${s.name}\\n${s.attendees || '?'} attendees · ${s.event_days || '?'} days"]\n`;

      // Category nodes
      for (const c of categories) {
        diagram += `  ${c.id}["${c.label}\\n${fmt(em[c.key])}"]\n`;
      }

      // Scope nodes
      if (parseFloat(s1) > 0) diagram += `  S1["Scope 1\\nDirect\\n${s1} t"]\n`;
      if (parseFloat(s2) > 0) diagram += `  S2["Scope 2\\nEnergy\\n${s2} t"]\n`;
      if (parseFloat(s3) > 0) diagram += `  S3["Scope 3\\nIndirect\\n${s3} t"]\n`;

      // Total node
      diagram += `  TOT(["Total\\n${fmt(total)}\\n${fmt(em.per_attendee_tco2e)}/attendee"])\n`;

      // Edges: event → categories
      for (const c of categories) {
        diagram += `  EVT --> ${c.id}\n`;
      }
      // Edges: categories → scopes
      for (const c of categories) {
        const scopeId = `S${c.scope}`;
        if (diagram.includes(`  ${scopeId}[`)) {
          diagram += `  ${c.id} --> ${scopeId}\n`;
        }
      }
      // Edges: scopes → total
      for (const sid of ['S1', 'S2', 'S3']) {
        if (diagram.includes(`  ${sid}[`)) {
          diagram += `  ${sid} --> TOT\n`;
        }
      }

      // Style
      diagram += `  style EVT fill:#1a9e6e,color:#fff,stroke:#15805a\n`;
      diagram += `  style TOT fill:#1a9e6e,color:#fff,stroke:#15805a\n`;
      if (diagram.includes('  S1[')) diagram += `  style S1 fill:#fee2e2,color:#dc2626,stroke:#dc2626\n`;
      if (diagram.includes('  S2[')) diagram += `  style S2 fill:#fef3c7,color:#d97706,stroke:#d97706\n`;
      if (diagram.includes('  S3[')) diagram += `  style S3 fill:#e0f2fe,color:#0369a1,stroke:#0369a1\n`;

      const el = document.getElementById('mermaidFlowchart');
      if (!el) return;
      el.innerHTML = '';

      try {
        const { svg } = await mermaid.render('mermaid-' + Date.now(), diagram);
        el.innerHTML = svg;
      } catch (err) {
        el.innerHTML = `<pre class="text-xs text-muted p-4 overflow-x-auto">${diagram}</pre>`;
      }
    },
  };
}
