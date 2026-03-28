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
    selectedScenarioId: localStorage.getItem('cc_selected_scenario_id') || null,
    selectedScenarioSyncing: false,
    selectedScenarioRequestToken: 0,
    suggestions: [],
    toast: { show: false, message: '', icon: 'fas fa-check text-accent' },
    agentsRunning: false,

    // -- Data & Exports --------------------------------------------------------
    agentStatus: [],
    agentHistory: [],

    // -- Dashboard -------------------------------------------------------------
    bestScenario: null,
    complianceScore: null,
    categoryChart: null,
    portfolioChart: null,
    comparisonChart: null,
    pathwayChart: null,
    scopeChart: null,
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
            if (scenRes.ok) {
              await this.applyScenarios(await scenRes.json(), this.selectedScenarioId, {
                syncSelected: true,
                renderDashboard: this.activeTab === 'dashboard',
              });
            }
          } else {
            this.token = null;
            localStorage.removeItem('cc_token');
            this.persistSelectedScenarioId(null);
          }
        } catch (e) {
          this.token = null;
          localStorage.removeItem('cc_token');
          this.persistSelectedScenarioId(null);
        }
      }
    },

    async switchTab(tabId) {
      this.activeTab = tabId;
      if (tabId === 'offsets') await this.loadOffsetData();
      if (tabId === 'data') await Promise.all([this.loadAgentStatus(), this.loadAgentHistory()]);
      if (tabId === 'dashboard') {
        if (this.token && this.scenarios.length === 0) {
          await this.loadScenarios(this.selectedScenarioId);
        } else if (this.selectedScenario || this.selectedScenarioId) {
          await this.syncSelectedScenarioFromDb(
            this.selectedScenario?.scenario_id || this.selectedScenarioId,
            { renderDashboard: true }
          );
        } else {
          this.scheduleDashboardRender();
        }
      }
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
            this.renderFlowchart(version, el);

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
      const portfolioCanvas = document.getElementById('portfolioChart');
      const comparisonCanvas = document.getElementById('comparisonChart');
      const hasScenarioCanvas = !this.selectedScenario || (
        categoryCanvas && categoryCanvas.clientWidth > 0 && categoryCanvas.clientHeight > 0
      );
      const hasPortfolioCanvas = this.scenarios.length === 0 || !portfolioCanvas || (
        portfolioCanvas.clientWidth > 0 && portfolioCanvas.clientHeight > 0
      );
      // If there are no scenarios the comparison canvas stays display:none — treat as ready (nothing to draw).
      const hasComparisonCanvas = this.scenarios.length === 0 || !comparisonCanvas || (
        comparisonCanvas.clientWidth > 0 && comparisonCanvas.clientHeight > 0
      );

      if (hasScenarioCanvas && hasPortfolioCanvas && hasComparisonCanvas) {
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
      localStorage.removeItem('cc_selected_scenario_id');
      this.scenarios = [];
      this.selectedScenario = null;
      this.selectedScenarioId = null;
      this.bestScenario = null;
      this.complianceScore = null;
      this.destroySelectedScenarioCharts();
      this.destroyPortfolioCharts();
    },

    // -- Toast -----------------------------------------------------------------
    showToast(message, icon = 'fas fa-check text-accent') {
      this.toast = { show: true, message, icon };
      setTimeout(() => this.toast.show = false, 3500);
    },

    // -- Scenarios -------------------------------------------------------------
    persistSelectedScenarioId(id = null) {
      this.selectedScenarioId = id || null;
      if (id) {
        localStorage.setItem('cc_selected_scenario_id', id);
      } else {
        localStorage.removeItem('cc_selected_scenario_id');
      }
    },

    syncScenarioDependents(scenario) {
      if (!scenario?.emissions) return;
      this.loadScenarioIntoFinCalc(scenario);
      this.complianceInput.total_tco2e = scenario.emissions.total_tco2e;
      this.complianceInput.attendees = scenario.attendees;
      this.complianceInput.event_days = scenario.event_days;
    },

    recomputeBestScenario() {
      this.bestScenario = this.scenarios.length > 0
        ? [...this.scenarios].sort((a, b) => (a.emissions?.total_tco2e || 0) - (b.emissions?.total_tco2e || 0))[0]
        : null;
    },

    mergeScenarioIntoCollection(scenario) {
      const idx = this.scenarios.findIndex(s => s.scenario_id === scenario.scenario_id);
      const next = [...this.scenarios];
      if (idx >= 0) {
        next[idx] = scenario;
      } else {
        next.unshift(scenario);
      }
      this.scenarios = next;
      this.recomputeBestScenario();
      return scenario;
    },

    async fetchScenarioById(scenarioId) {
      if (!scenarioId || !this.token) return null;
      const res = await fetch(`${API}/api/scenarios/${scenarioId}`, {
        headers: { 'Authorization': `Bearer ${this.token}` },
      });
      if (!res.ok) return null;
      return await res.json();
    },

    async syncSelectedScenarioFromDb(scenarioId = null, { renderDashboard = true } = {}) {
      const targetId = scenarioId || this.selectedScenario?.scenario_id || this.selectedScenarioId;
      if (!targetId || !this.token) {
        if (renderDashboard && this.activeTab === 'dashboard') this.scheduleDashboardRender();
        return this.selectedScenario;
      }

      const requestToken = ++this.selectedScenarioRequestToken;
      this.selectedScenarioSyncing = true;

      try {
        const scenario = await this.fetchScenarioById(targetId);
        if (!scenario || requestToken !== this.selectedScenarioRequestToken) return this.selectedScenario;

        this.mergeScenarioIntoCollection(scenario);
        this.selectedScenario = scenario;
        this.persistSelectedScenarioId(scenario.scenario_id);
        this.syncScenarioDependents(scenario);
        return scenario;
      } catch (e) {
        console.error('Failed to synchronize selected scenario:', e);
        return this.selectedScenario;
      } finally {
        if (requestToken === this.selectedScenarioRequestToken) {
          this.selectedScenarioSyncing = false;
          if (renderDashboard && this.activeTab === 'dashboard') this.scheduleDashboardRender();
        }
      }
    },

    async applyScenarios(list, preferredScenarioId = null, { syncSelected = true, renderDashboard = true } = {}) {
      const rememberedId = preferredScenarioId || this.selectedScenario?.scenario_id || this.selectedScenarioId || null;
      this.scenarios = list;
      if (list.length > 0) {
        this.recomputeBestScenario();
        this.selectedScenario = rememberedId
          ? (list.find(s => s.scenario_id === rememberedId) || list[0])
          : list[0];
        if (this.selectedScenario) {
          this.persistSelectedScenarioId(this.selectedScenario.scenario_id);
          this.syncScenarioDependents(this.selectedScenario);
          if (syncSelected) {
            await this.syncSelectedScenarioFromDb(this.selectedScenario.scenario_id, { renderDashboard });
            return;
          }
        }
      } else {
        this.selectedScenario = null;
        this.persistSelectedScenarioId(null);
        this.recomputeBestScenario();
        this.destroySelectedScenarioCharts();
        this.destroyPortfolioCharts();
      }
      if (renderDashboard) this.scheduleDashboardRender();
    },

    async loadScenarios(preferredScenarioId = null) {
      try {
        const res = await fetch(`${API}/api/scenarios`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        if (res.ok) {
          await this.applyScenarios(await res.json(), preferredScenarioId, {
            syncSelected: true,
            renderDashboard: this.activeTab === 'dashboard',
          });
        }
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
        this.persistSelectedScenarioId(scenario.scenario_id);
        this.syncScenarioDependents(scenario);
        this.recomputeBestScenario();
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
        this.mergeScenarioIntoCollection(cloned);
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
      if (this.selectedScenario) {
        this.persistSelectedScenarioId(this.selectedScenario.scenario_id);
        this.syncScenarioDependents(this.selectedScenario);
      } else {
        this.persistSelectedScenarioId(null);
      }
      this.recomputeBestScenario();
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

    async selectScenario(s) {
      this.selectedScenario = s;
      this.persistSelectedScenarioId(s.scenario_id);
      this.suggestions = [];
      this.syncScenarioDependents(s);
      this.scheduleDashboardRender();
      await this.syncSelectedScenarioFromDb(s.scenario_id, { renderDashboard: this.activeTab === 'dashboard' });
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

    shortScenarioName(name, maxLength = 18) {
      if (!name) return 'Untitled';
      return name.length > maxLength ? `${name.slice(0, maxLength)}...` : name;
    },

    reductionFactorForCategory(key) {
      return {
        travel_tco2e: 0.22,
        venue_energy_tco2e: 0.45,
        accommodation_tco2e: 0.18,
        catering_tco2e: 0.35,
        materials_waste_tco2e: 0.40,
        equipment_tco2e: 0.25,
        swag_tco2e: 0.50,
      }[key] || 0;
    },

    portfolioScenarioRows() {
      const rows = this.scenarios
        .map((scenario) => {
          const totalTco2e = scenario.emissions?.total_tco2e || 0;
          const intensityKg = (scenario.emissions?.per_attendee_tco2e || 0) * 1000;
          const perDayKg = (scenario.emissions?.per_attendee_day_tco2e || 0) * 1000;
          const hotspot = this.topEmissionSource(scenario);

          return {
            scenario,
            scenario_id: scenario.scenario_id,
            name: scenario.name,
            shortName: this.shortScenarioName(scenario.name),
            totalTco2e,
            intensityKg,
            perDayKg,
            attendees: scenario.attendees || 0,
            eventDays: scenario.event_days || 0,
            hotspotLabel: hotspot.label,
            hotspotValue: hotspot.value,
            isSelected: this.selectedScenario?.scenario_id === scenario.scenario_id,
          };
        })
        .sort((a, b) => {
          if (a.totalTco2e !== b.totalTco2e) return a.totalTco2e - b.totalTco2e;
          return a.name.localeCompare(b.name);
        });

      const bestTotal = rows[0]?.totalTco2e || 0;
      return rows.map((row, index) => ({
        ...row,
        rank: index + 1,
        gapToBestPct: bestTotal > 0 && row.totalTco2e > 0 ? ((row.totalTco2e - bestTotal) / row.totalTco2e) * 100 : 0,
      }));
    },

    selectedScenarioCategoryRows() {
      const s = this.selectedScenario;
      if (!s?.emissions) return [];

      return this.emissionCategories
        .map(cat => ({
          key: cat.key,
          label: cat.label,
          color: cat.color,
          value: s.emissions[cat.key] || 0,
        }))
        .filter(row => row.value > 0)
        .sort((a, b) => b.value - a.value);
    },

    selectedScenarioScopeRows() {
      const scopes = this.selectedScenario?.emissions?.scopes;
      if (!scopes) return [];

      return [
        { label: 'Scope 1 (Direct)', value: scopes.scope1_tco2e || 0, color: '#dc2626' },
        { label: 'Scope 2 (Energy)', value: scopes.scope2_tco2e || 0, color: '#d97706' },
        { label: 'Scope 3 (Indirect)', value: scopes.scope3_tco2e || 0, color: '#0369a1' },
      ];
    },

    selectedScenarioOpportunityRows() {
      const s = this.selectedScenario;
      if (!s?.emissions) return [];

      return this.emissionCategories
        .map(cat => {
          const base = s.emissions[cat.key] || 0;
          return {
            key: cat.key,
            label: cat.label,
            color: cat.color,
            value: +(base * this.reductionFactorForCategory(cat.key)).toFixed(4),
          };
        })
        .filter(row => row.value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, 6);
    },

    selectedScenarioFactorRows() {
      const snap = this.selectedScenario?.factors_snapshot;
      if (!snap || !Object.keys(snap).length) return [];

      return [
        { label: 'Long-haul flight', unit: 'kg/pkm', value: snap.travel_long_haul_economy_kg_per_pkm, color: '#0ea5e9' },
        { label: 'Short-haul flight', unit: 'kg/pkm', value: snap.travel_short_haul_economy_kg_per_pkm, color: '#38bdf8' },
        { label: 'Car (petrol)', unit: 'kg/pkm', value: snap.travel_car_petrol_kg_per_pkm, color: '#f59e0b' },
        { label: `Grid (${(snap.venue_grid_region || 'global').replace('_', ' ')})`, unit: 'kg/kWh', value: snap.venue_grid_kg_per_kwh, color: '#eab308' },
        { label: `Catering (${(snap.catering_type || 'mixed').replace(/_/g, ' ')})`, unit: 'kg/meal', value: snap.catering_kg_per_meal, color: '#22c55e' },
        { label: 'Accommodation', unit: 'kg/room-night÷10', value: (snap.accommodation_kg_per_room_night || 0) / 10, color: '#8b5cf6' },
        { label: 'Waste (landfill)', unit: 'kg/kg', value: snap.waste_landfill_kg_per_kg, color: '#6b7280' },
      ].filter(row => row.value > 0);
    },

    flowchartCategoryRows(scenario) {
      if (!scenario?.emissions) return [];

      const meta = {
        travel_tco2e: { id: 'TR', target: 'S3' },
        venue_energy_tco2e: { id: 'VE', target: 'S2' },
        accommodation_tco2e: { id: 'AC', target: 'S3' },
        catering_tco2e: { id: 'CA', target: 'S3' },
        materials_waste_tco2e: { id: 'WA', target: 'S3' },
        equipment_tco2e: { id: 'EQ', target: 'TOT', note: 'mixed scopes' },
        swag_tco2e: { id: 'SW', target: 'S3' },
      };

      return this.emissionCategories
        .map((cat) => {
          const config = meta[cat.key] || { id: cat.key.toUpperCase(), target: 'TOT' };
          return {
            key: cat.key,
            label: cat.label,
            color: cat.color,
            id: config.id,
            target: config.target,
            note: config.note || '',
            value: scenario.emissions[cat.key] || 0,
          };
        })
        .filter(row => row.value > 0);
    },

    scenarioRank(scenario) {
      if (!scenario || this.scenarios.length === 0) return 0;
      const row = this.portfolioScenarioRows().find(s => s.scenario_id === scenario.scenario_id);
      return row ? row.rank : 0;
    },

    scenarioGapToBest(scenario) {
      if (!scenario) return 0;
      const row = this.portfolioScenarioRows().find(s => s.scenario_id === scenario.scenario_id);
      return row ? row.gapToBestPct : 0;
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
      return this.emissionCategories.reduce((sum, cat) => {
        const value = scenario.emissions[cat.key] || 0;
        const factor = this.reductionFactorForCategory(cat.key);
        return sum + value * factor;
      }, 0);
    },

    dashboardSavingsSignal(scenario) {
      if (!scenario?.emissions) return null;
      if (this.finResult && this.finCalc.linked_scenario_id === scenario.scenario_id) {
        return Math.round(this.finResult.total_financial_savings_usd);
      }
      return Math.round((scenario.emissions.total_tco2e || 0) * 0.3 * 25 * 0.74);
    },

    dashboardSavingsLabel(scenario) {
      if (!scenario?.emissions) return 'not available';
      if (this.finResult && this.finCalc.linked_scenario_id === scenario.scenario_id) {
        return 'from linked financial analysis';
      }
      return 'modeled at 30% reduction';
    },

    destroyDashboardChart(key) {
      if (this[key]) {
        this[key].destroy();
        this[key] = null;
      }
    },

    destroySelectedScenarioCharts() {
      ['categoryChart', 'pathwayChart', 'scopeChart', 'opportunityChart', 'factorsChart'].forEach(key => this.destroyDashboardChart(key));
    },

    destroyPortfolioCharts() {
      ['portfolioChart', 'comparisonChart'].forEach(key => this.destroyDashboardChart(key));
    },

    // -- Charts ----------------------------------------------------------------
    drawCharts(resetError = true, reportErrors = true) {
      if (resetError) this.dashboardChartError = '';

      if (typeof Chart === 'undefined') {
        if (reportErrors) this.dashboardChartError = 'Chart.js failed to load. Check internet/CDN access and refresh.';
        return;
      }

      try {
        if (this.scenarios.length > 0) {
          this.drawPortfolioChart();
          this.drawComparisonChart();
        } else {
          this.destroyPortfolioCharts();
        }

        if (this.selectedScenario) {
          this.drawCategoryChart();
          this.drawPathwayChart();
          this.drawScopeChart();
          this.drawOpportunityChart();
          this.drawFactorsChart();
        } else {
          this.destroySelectedScenarioCharts();
        }

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
      const rows = this.selectedScenarioCategoryRows();
      const ctx = document.getElementById('categoryChart');
      if (!ctx || rows.length === 0) {
        this.destroyDashboardChart('categoryChart');
        return;
      }
      this.destroyDashboardChart('categoryChart');

      const labels = rows.map(row => row.label);
      const data = rows.map(row => row.value);
      const colors = rows.map(row => row.color);

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
                label: (tooltipItem) => {
                  const total = data.reduce((sum, value) => sum + value, 0) || 1;
                  return ` ${tooltipItem.label}: ${Number(tooltipItem.raw).toFixed(3)} tCO2e (${((tooltipItem.raw / total) * 100).toFixed(1)}%)`;
                },
              },
            },
          },
        },
      });
    },

    drawScopeChart() {
      const rows = this.selectedScenarioScopeRows();
      const ctx = document.getElementById('scopeChart');
      if (!ctx || rows.length === 0) {
        this.destroyDashboardChart('scopeChart');
        return;
      }
      this.destroyDashboardChart('scopeChart');

      this.scopeChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: rows.map(row => row.label),
          datasets: [{ data: rows.map(row => row.value), backgroundColor: rows.map(row => row.color), borderRadius: 6, barThickness: 40 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          scales: {
            x: { ticks: { color: '#6b7280', callback: value => `${Number(value).toFixed(2)} t` }, grid: { color: '#e5e7eb' } },
            y: { ticks: { color: '#6b7280', font: { size: 11 } }, grid: { display: false } },
          },
          plugins: { legend: { display: false } },
        },
      });
    },

    drawPortfolioChart() {
      const ctx = document.getElementById('portfolioChart');
      const rows = this.portfolioScenarioRows();
      if (!ctx || rows.length === 0) {
        this.destroyDashboardChart('portfolioChart');
        return;
      }
      this.destroyDashboardChart('portfolioChart');

      this.portfolioChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: rows.map(row => row.shortName),
          datasets: [
            {
              label: 'Total tCO2e',
              data: rows.map(row => +row.totalTco2e.toFixed(3)),
              backgroundColor: rows.map(row => row.isSelected ? '#1a9e6e' : 'rgba(26,158,110,0.24)'),
              borderColor: rows.map(row => row.isSelected ? '#0f6b49' : '#1a9e6e'),
              borderWidth: rows.map(row => row.isSelected ? 2 : 1),
              borderRadius: 6,
              yAxisID: 'yTotal',
            },
            {
              type: 'line',
              label: 'kg CO2e / attendee',
              data: rows.map(row => +row.intensityKg.toFixed(1)),
              borderColor: '#0369a1',
              backgroundColor: 'transparent',
              borderDash: [6, 4],
              tension: 0.28,
              pointRadius: rows.map(row => row.isSelected ? 5 : 3),
              pointBackgroundColor: rows.map(row => row.isSelected ? '#0f172a' : '#0369a1'),
              pointBorderColor: rows.map(row => row.isSelected ? '#1a9e6e' : '#0369a1'),
              pointBorderWidth: rows.map(row => row.isSelected ? 2 : 1),
              yAxisID: 'yIntensity',
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            x: { ticks: { color: '#6b7280', font: { size: 10 } }, grid: { display: false } },
            yTotal: {
              position: 'left',
              ticks: { color: '#1a9e6e', callback: value => `${Number(value).toFixed(1)} t` },
              grid: { color: '#e5e7eb' },
            },
            yIntensity: {
              position: 'right',
              ticks: { color: '#0369a1', callback: value => `${Number(value).toFixed(0)} kg` },
              grid: { drawOnChartArea: false },
            },
          },
          plugins: {
            legend: { labels: { color: '#6b7280', boxWidth: 10, font: { size: 10 } } },
            tooltip: {
              callbacks: {
                title: items => rows[items[0]?.dataIndex]?.name || items[0]?.label || '',
                afterBody: items => {
                  const row = rows[items[0]?.dataIndex];
                  if (!row) return [];
                  return [
                    `Rank #${row.rank} of ${rows.length}`,
                    `${row.attendees} attendees · ${row.eventDays} day${row.eventDays === 1 ? '' : 's'}`,
                    `Top hotspot: ${row.hotspotLabel}`,
                  ];
                },
              },
            },
          },
        },
      });
    },

    drawComparisonChart() {
      const ctx = document.getElementById('comparisonChart');
      const rows = this.portfolioScenarioRows();
      if (!ctx || rows.length === 0) {
        this.destroyDashboardChart('comparisonChart');
        return;
      }
      this.destroyDashboardChart('comparisonChart');

      const datasets = this.emissionCategories.map((cat) => ({
        label: cat.label,
        data: rows.map(row => +(row.scenario.emissions[cat.key] || 0).toFixed(3)),
        backgroundColor: `${cat.color}cc`,
        borderColor: cat.color,
        borderWidth: 1,
        borderRadius: 4,
      }));

      this.comparisonChart = new Chart(ctx, {
        type: 'bar',
        data: { labels: rows.map(row => row.shortName), datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          interaction: { mode: 'index', intersect: false },
          scales: {
            x: {
              stacked: true,
              ticks: { color: '#6b7280', font: { size: 10 }, callback: value => `${Number(value).toFixed(1)} t` },
              grid: { color: '#e5e7eb' },
            },
            y: {
              stacked: true,
              ticks: { color: '#6b7280', font: { size: 10 } },
              grid: { display: false },
            },
          },
          plugins: {
            legend: { labels: { color: '#6b7280', font: { size: 10 }, boxWidth: 10 } },
            tooltip: {
              callbacks: {
                title: items => rows[items[0]?.dataIndex]?.name || items[0]?.label || '',
                footer: items => {
                  const row = rows[items[0]?.dataIndex];
                  return row ? `Total: ${row.totalTco2e.toFixed(3)} tCO2e` : '';
                },
              },
            },
          },
        },
      });
    },

    drawOpportunityChart() {
      const rows = this.selectedScenarioOpportunityRows();
      const ctx = document.getElementById('opportunityChart');
      if (!ctx || rows.length === 0) {
        this.destroyDashboardChart('opportunityChart');
        return;
      }
      this.destroyDashboardChart('opportunityChart');

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
            x: { ticks: { color: '#6b7280', callback: value => `${Number(value).toFixed(2)} t` }, grid: { color: '#e5e7eb' } },
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
      if (!s) {
        this.destroyDashboardChart('pathwayChart');
        return;
      }
      const ctx = document.getElementById('pathwayChart');
      if (!ctx) {
        this.destroyDashboardChart('pathwayChart');
        return;
      }
      this.destroyDashboardChart('pathwayChart');

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
              ticks: { color: '#6b7280', callback: value => `${Number(value).toFixed(1)} t` },
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
      this.destroyDashboardChart('factorsChart');
      const rows = this.selectedScenarioFactorRows();
      const ctx = document.getElementById('factorsChart');
      if (!ctx || rows.length === 0) return;

      const version = this.selectedScenario?.factors_snapshot?.ef_version ? ` · EF v${this.selectedScenario.factors_snapshot.ef_version}` : '';
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
              ticks: { color: '#6b7280', font: { size: 10 }, callback: value => Number(value).toFixed(3) },
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
      const safe = String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
      return safe
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
      if (!this.token) {
        this.showToast('Sign in to save and calculate financial reports', 'fas fa-triangle-exclamation text-gold');
        return;
      }
      this.finLoading = true;
      try {
        const reduced = this.finCalc.baseline * (1 - this.finCalc.reduction_pct / 100);
        const res = await fetch(`${API}/api/financial/savings`, {
          method: 'POST',
          headers: this.authHeaders(),
          body: JSON.stringify({
            scenario_id: this.finCalc.linked_scenario_id || null,
            baseline_tco2e: this.finCalc.baseline,
            reduced_tco2e: reduced,
            region: this.finCalc.region,
            energy_kwh_saved: this.finCalc.energy_kwh || 0,
            meal_switches: this.finCalc.meal_switches || 0,
            attendees: this.complianceInput.attendees || 0,
            actions_taken: this.finCalc.actions,
          }),
        });
        if (!res.ok) throw new Error(await res.text());
        this.finResult = await res.json();
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
      if (!this.token) {
        this.showToast('Sign in to refresh factors', 'fas fa-triangle-exclamation text-gold');
        return;
      }
      this.agentsRunning = true;
      this.showToast('Refreshing factors and recalculating scenarios...', 'fas fa-sync-alt text-blue');
      const previouslySelectedId = this.selectedScenario?.scenario_id || null;
      let agentOk = false;

      // Step 1: refresh global emission factors via TinyFish (non-fatal if it fails)
      try {
        const runRes = await fetch(`${API}/api/agents/run/sync?force=true`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
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
            await this.applyScenarios(recalc.scenarios, previouslySelectedId, {
              syncSelected: true,
              renderDashboard: this.activeTab === 'dashboard',
            });
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

      try { await Promise.all([this.loadAgentStatus(), this.loadAgentHistory()]); } catch (_) {}
      this.agentsRunning = false;
    },

    async refreshAgentsForceful() {
      if (!this.token) {
        this.showToast('Sign in to refresh factors', 'fas fa-triangle-exclamation text-gold');
        return;
      }
      this.agentsRunning = true;
      this.showToast('Force re-fetching all agents...', 'fas fa-bolt text-gold');
      try {
        await fetch(`${API}/api/agents/run?force=true`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        setTimeout(async () => {
          this.agentsRunning = false;
          await Promise.all([this.loadAgentStatus(), this.loadAgentHistory()]);
          this.showToast('Force refresh dispatched', 'fas fa-bolt text-gold');
        }, 4000);
      } catch {
        this.agentsRunning = false;
      }
    },

    // -- Data & Exports --------------------------------------------------------
    async loadAgentStatus() {
      if (!this.token) {
        this.agentStatus = [];
        return;
      }
      try {
        const res = await fetch(`${API}/api/agents/status`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
        if (res.ok) this.agentStatus = await res.json();
      } catch (e) {
        console.error('Failed to load agent status:', e);
      }
    },

    async loadAgentHistory() {
      if (!this.token) {
        this.agentHistory = [];
        return;
      }
      try {
        const res = await fetch(`${API}/api/agents/history?limit=50`, {
          headers: { 'Authorization': `Bearer ${this.token}` },
        });
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

    async downloadFileAuth(url, filename) {
      if (!this.token) {
        this.showToast('Sign in to download this export', 'fas fa-triangle-exclamation text-gold');
        return;
      }
      try {
        const response = await fetch(url, { headers: { 'Authorization': `Bearer ${this.token}` } });
        if (!response.ok) throw new Error('Download request failed');
        const blob = await response.blob();
        const objUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = objUrl;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(objUrl);
      } catch (_) {
        this.showToast('Download failed', 'fas fa-triangle-exclamation text-red');
      }
    },

    downloadScenarioReport() {
      if (!this.selectedScenario) {
        this.showToast('Select a scenario first', 'fas fa-triangle-exclamation text-gold');
        return;
      }
      this.downloadFileAuth(
        `/api/exports/scenarios/${this.selectedScenario.scenario_id}.xlsx`,
        `report_${this.selectedScenario.scenario_id}.xlsx`
      );
    },

    // -- Mermaid flowchart -----------------------------------------------------
    async renderFlowchart(version = 0, rootEl = null) {
      const el = document.getElementById('mermaidFlowchart');
      if (!el) return;

      const s = this.selectedScenario;
      if (!s) {
        el.innerHTML = '<div class="text-xs text-muted py-8">Select a scenario to generate its flowchart.</div>';
        return;
      }

      const em = s.emissions;
      const total = em.total_tco2e || 0.001;
      const fmt = v => (v || 0).toFixed(3) + ' t';
      const scenarioId = s.scenario_id;
      const categories = this.flowchartCategoryRows(s);
      const scenarioLabel = `${s.name}\\n${s.attendees || '?'} attendees · ${s.event_days || '?'} days`;

      const scopes = em.scopes || {};
      const s1 = (scopes.scope1_tco2e || 0).toFixed(3);
      const s2 = (scopes.scope2_tco2e || 0).toFixed(3);
      const s3 = (scopes.scope3_tco2e || 0).toFixed(3);

      let diagram = `flowchart TD\n`;
      diagram += `  EVT["🏢 ${scenarioLabel}"]\n`;

      // Category nodes
      for (const c of categories) {
        const note = c.note ? `\\n${c.note}` : '';
        diagram += `  ${c.id}["${c.label}\\n${fmt(c.value)}${note}"]\n`;
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
      // Edges: categories → scopes/total
      for (const c of categories) {
        const targetId = c.target || 'TOT';
        if (targetId === 'TOT') {
          diagram += `  ${c.id} --> TOT\n`;
        } else if (diagram.includes(`  ${targetId}[`)) {
          diagram += `  ${c.id} --> ${targetId}\n`;
        } else {
          diagram += `  ${c.id} --> TOT\n`;
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
      for (const c of categories) {
        diagram += `  style ${c.id} fill:${c.color}22,color:#111827,stroke:${c.color}\n`;
      }
      el.innerHTML = '';

      try {
        const renderId = `mermaid-${scenarioId}-${version || Date.now()}`;
        const { svg } = await mermaid.render(renderId, diagram);
        if ((rootEl && version && rootEl._chartRenderVersion !== version) || this.selectedScenario?.scenario_id !== scenarioId) return;
        el.innerHTML = svg;
      } catch (err) {
        if ((rootEl && version && rootEl._chartRenderVersion !== version) || this.selectedScenario?.scenario_id !== scenarioId) return;
        el.innerHTML = `<pre class="text-xs text-muted p-4 overflow-x-auto">${diagram}</pre>`;
      }
    },
  };
}
