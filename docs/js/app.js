/**
 * LEWDSS · DECISION LAB — Frontend Application Controller
 * Inspired by TerraSense ML Architecture
 * 
 * Provides:
 * - Multi-tab view routing (Overview, Risk Inference, Monitoring Zones, Observations,
 *   Alerts & SOPs, Model Diagnostics, Threshold Settings, State-Space DLM, SHAP, RAG AI, About).
 * - Dual-mode scenario inference: Live REST API when running server, client-side
 *   mathematical engine when hosted statically (e.g., GitHub Pages).
 * - Interactive 1D Kalman Filter State-Space Soil Moisture Simulator.
 * - Floating GeoGuard RAG Assistant window & embedded RAG integration.
 * - NASA GLC 144 events catalog browser with instant scenario loader.
 */

// Application State
const state = {
  currentView: "overview",
  selectedDistrict: "Wayanad",
  selectedModelFamily: "LogisticRegression",
  selectedFeatureSet: "FS3_Full",
  districtData: null,
  explainabilityData: null,
  allObservations: [],
  filteredObservations: [],
  currentObsDistrictFilter: "all",
  currentObsSearchQuery: "",
};

// District to Spatial Validation Fold mapping
const DISTRICT_FOLD_MAP = {
  "Wayanad": "Fold_A1",
  "Idukki": "Fold_A2",
  "Kodagu": "Fold_A3",
  "East Sikkim": "Fold_B1",
  "West Sikkim": "Fold_B2",
  "East Khasi Hills": "Fold_B3",
};

// View Title Dictionary
const VIEW_TITLES = {
  "overview": "Overview & Operational Summary",
  "inference": "Relative Landslide Susceptibility Estimator",
  "zones": "Registered Monitoring Zones (6 Districts)",
  "observations": "Sensor Observations & Historical Event Catalog",
  "alerts": "Alert Center & Operational SOPs",
  "diagnostics": "Model Diagnostics & Spatial CV Benchmark",
  "shap": "Explainable AI (SHAP Feature Attribution)",
  "rag": "Decision Support Assistant (GeoGuard)",
};

// Standard Operating Procedures Guidance
const SOP_GUIDANCE = {
  LOW: {
    tier_name: "Minimal Relative Susceptibility",
    badge_color: "low",
    administrative_status: "Normal Seasonal Monitoring",
    community_actions: [
      "Maintain routine clearance of roadside ditches, culverts, and domestic rainwater drains.",
      "Inspect boundary retaining walls and terraces for pre-existing tension cracks or soil settling.",
      "Report uncharacteristic water ponding or muddy seepage near residential slopes to local Gram Panchayat officials.",
    ],
    infrastructure_actions: [
      "Normal traffic operations on ghat and mountain roads.",
      "Routine maintenance inspection of slope reinforcement netting and culverts along key highway corridors.",
    ],
  },
  ELEVATED: {
    tier_name: "Elevated Relative Susceptibility",
    badge_color: "elevated",
    administrative_status: "Heightened Vigilance & Advisory Mode",
    community_actions: [
      "Advise residents living near steep or modified slopes to monitor for fresh ground cracks.",
      "Avoid non-essential nighttime travel along steep mountain roads during continuous rainfall.",
      "Ensure household emergency battery packs, flashlights, and communications remain charged.",
    ],
    infrastructure_actions: [
      "Deploy road maintenance inspection teams along vulnerable highway stretches with known slide history.",
      "Verify that earthmoving equipment and operators are on stand-by at taluk public works depots.",
      "Install temporary cautionary signage along steep road cuttings with loose boulders or saturated soils.",
    ],
  },
  HIGH: {
    tier_name: "High Relative Susceptibility",
    badge_color: "high",
    administrative_status: "Preparedness Advisory & Resource Standby",
    community_actions: [
      "Keep essential medications, identity documents, and emergency supplies accessible.",
      "Heed official notifications from District Collector / DDMA regarding localized precautionary relocation.",
      "Immediately report rapid water color changes (sudden mud surges in clear mountain streams) or ground rumbling.",
      "Stay clear of river channels and steep ravines susceptible to debris flows during intense cloudbursts.",
    ],
    infrastructure_actions: [
      "Position heavy earthmoving equipment and debris clearance squads at strategic highway junctions.",
      "Coordinate with Traffic Police for restricted/regulated heavy-vehicle movement on ghat routes.",
      "Inspect bridge abutments and mountain stream crossings for debris damming or backwater accumulation.",
    ],
  },
};

const modelCache = new Map();

// ---------------------------------------------------------------------------
// Initialization & Navigation Routing
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupModelControls();
  loadDistrict(state.selectedDistrict);
  loadAllObservations();
  initSimulations();

  // Handle URL hash on initial load
  const initialHash = window.location.hash.replace("#", "");
  if (initialHash && VIEW_TITLES[initialHash]) {
    navigateTo(initialHash);
  }
});

function setupNavigation() {
  const navLinks = document.querySelectorAll(".sidebar-nav .nav-link");
  navLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const targetView = link.getAttribute("data-view");
      navigateTo(targetView);
    });
  });

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "");
    if (hash && VIEW_TITLES[hash] && hash !== state.currentView) {
      navigateTo(hash, false);
    }
  });
}

function navigateTo(viewId, updateHash = true) {
  if (!VIEW_TITLES[viewId]) viewId = "overview";
  state.currentView = viewId;

  // 1. Update navigation active state
  document.querySelectorAll(".sidebar-nav .nav-link").forEach((link) => {
    if (link.getAttribute("data-view") === viewId) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });

  // 2. Switch visible view
  document.querySelectorAll(".tab-view").forEach((section) => {
    section.classList.remove("active");
  });
  const activeSection = document.getElementById(`view-${viewId}`);
  if (activeSection) {
    activeSection.classList.add("active");
  }

  // 3. Update topbar breadcrumb
  const breadcrumb = document.getElementById("topbar-active-title");
  if (breadcrumb) {
    breadcrumb.textContent = VIEW_TITLES[viewId];
  }

  // 4. Update browser URL hash
  if (updateHash) {
    window.location.hash = viewId;
  }

  // 5. Scroll to top of main area
  window.scrollTo({ top: 0, behavior: "smooth" });

  // Close mobile sidebar if open
  const sidebar = document.getElementById("app-sidebar");
  if (sidebar) sidebar.classList.remove("mobile-open");
}

window.navigateTo = navigateTo;

function toggleMobileSidebar() {
  const sidebar = document.getElementById("app-sidebar");
  if (sidebar) {
    sidebar.classList.toggle("mobile-open");
  }
}
window.toggleMobileSidebar = toggleMobileSidebar;

// ---------------------------------------------------------------------------
// Model Controls & District Selection
// ---------------------------------------------------------------------------

function setupModelControls() {
  const selectModel = document.getElementById("select-model-family");
  const selectFeatureSet = document.getElementById("select-feature-set");

  if (selectModel) {
    selectModel.addEventListener("change", (e) => {
      state.selectedModelFamily = e.target.value;
      updateShapView();
    });
  }

  if (selectFeatureSet) {
    selectFeatureSet.addEventListener("change", (e) => {
      state.selectedFeatureSet = e.target.value;
    });
  }
}

function selectDistrict(dName) {
  state.selectedDistrict = dName;
  document.querySelectorAll(".district-selection-strip .btn-dist").forEach((btn) => {
    if (btn.getAttribute("data-district") === dName) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  loadDistrict(dName);
}
window.selectDistrict = selectDistrict;

function loadZoneAndNavigate(zoneName) {
  selectDistrict(zoneName);
  navigateTo("inference");
}
window.loadZoneAndNavigate = loadZoneAndNavigate;

// ---------------------------------------------------------------------------
// Data Fetching: District Profiles & SHAP Attributions
// ---------------------------------------------------------------------------

async function loadDistrict(districtName) {
  try {
    let distData = null;
    let expData = null;

    const isStaticHost =
      window.location.protocol === "file:" ||
      window.location.hostname.endsWith("github.io") ||
      window.location.hostname.endsWith("pages.dev");

    // Try API first if not strictly static
    if (!isStaticHost) {
      try {
        const distRes = await fetch(`/api/districts/${encodeURIComponent(districtName)}`);
        if (distRes.ok) distData = await distRes.json();
      } catch (_) {}
    }

    // Static JSON fallback
    if (!distData) {
      const safeName = districtName.replace(/ /g, "_");
      let res = await fetch(`./data/districts/${encodeURIComponent(districtName)}.json`);
      if (!res.ok) res = await fetch(`./data/districts/${safeName}.json`);
      if (res.ok) distData = await res.json();
    }

    if (distData) {
      state.districtData = distData;
      resetToDistrictMedian();
    }

    // Load explainability data
    if (!isStaticHost) {
      try {
        const expRes = await fetch(`/api/explainability/${encodeURIComponent(districtName)}`);
        if (expRes.ok) expData = await expRes.json();
      } catch (_) {}
    }

    if (!expData) {
      const safeName = districtName.replace(/ /g, "_");
      let expRes = await fetch(`./data/explainability/${encodeURIComponent(districtName)}.json`);
      if (!expRes.ok) expRes = await fetch(`./data/explainability/${safeName}.json`);
      if (expRes.ok) expData = await expRes.json();
    }

    if (expData) {
      state.explainabilityData = expData;
      updateShapView();
    }
  } catch (err) {
    console.error("Error loading district:", err);
  }
}

function resetToDistrictMedian() {
  const d = state.districtData;
  if (!d) return;

  const topo = d.topographic_profile || {};
  document.getElementById("inp-elev").value = Math.round(topo.elevation_mean_m || 1050);
  document.getElementById("inp-slope").value = (topo.slope_mean_deg || 22.5).toFixed(1);

  if (d.historical_positive_events && d.historical_positive_events.length > 0) {
    const midIdx = Math.floor(d.historical_positive_events.length / 2);
    const midEv = d.historical_positive_events[midIdx];
    document.getElementById("inp-rain3d").value = midEv.observed_rain_3d_mm;
    document.getElementById("inp-rain7d").value = midEv.observed_rain_7d_mm;
    document.getElementById("inp-rain15d").value = midEv.observed_rain_15d_mm;
  } else {
    document.getElementById("inp-rain3d").value = 45.0;
    document.getElementById("inp-rain7d").value = 110.0;
    document.getElementById("inp-rain15d").value = 210.0;
  }
}
window.resetToDistrictMedian = resetToDistrictMedian;

function loadHistoricalExtreme() {
  const d = state.districtData;
  if (!d) return;

  const topo = d.topographic_profile || {};
  document.getElementById("inp-elev").value = Math.round(topo.elevation_max_m ? topo.elevation_max_m * 0.85 : 1450);
  document.getElementById("inp-slope").value = 34.5;
  document.getElementById("inp-rain3d").value = 210.0;
  document.getElementById("inp-rain7d").value = 380.0;
  document.getElementById("inp-rain15d").value = 520.0;

  evaluateScenario();
}
window.loadHistoricalExtreme = loadHistoricalExtreme;

// ---------------------------------------------------------------------------
// All Observations Table (View 4 - All 6 Monitored Districts)
// ---------------------------------------------------------------------------

const FALLBACK_OBSERVATIONS = [
  { district: "Wayanad", event_date: "2018-08-08", observed_slope_deg: 27.6, observed_elevation_m: 873.0, observed_rain_3d_mm: 85.0, observed_rain_7d_mm: 156.8, observed_rain_15d_mm: 324.7, source: "NASA GLC" },
  { district: "Wayanad", event_date: "2009-07-15", observed_slope_deg: 2.4, observed_elevation_m: 759.7, observed_rain_3d_mm: 207.8, observed_rain_7d_mm: 260.0, observed_rain_15d_mm: 656.9, source: "NASA GLC" },
  { district: "Wayanad", event_date: "2018-08-09", observed_slope_deg: 8.6, observed_elevation_m: 840.8, observed_rain_3d_mm: 147.1, observed_rain_7d_mm: 147.1, observed_rain_15d_mm: 336.8, source: "NASA GLC" },
  { district: "Idukki", event_date: "2011-06-02", observed_slope_deg: 20.2, observed_elevation_m: 92.7, observed_rain_3d_mm: 349.4, observed_rain_7d_mm: 425.3, observed_rain_15d_mm: 498.7, source: "NASA GLC" },
  { district: "Idukki", event_date: "2018-08-15", observed_slope_deg: 1.6, observed_elevation_m: 68.4, observed_rain_3d_mm: 225.3, observed_rain_7d_mm: 362.8, observed_rain_15d_mm: 469.8, source: "NASA GLC" },
  { district: "Idukki", event_date: "2018-08-08", observed_slope_deg: 5.2, observed_elevation_m: 55.7, observed_rain_3d_mm: 76.9, observed_rain_7d_mm: 105.7, observed_rain_15d_mm: 309.9, source: "NASA GLC" },
  { district: "Kodagu", event_date: "2014-05-25", observed_slope_deg: 6.3, observed_elevation_m: 951.5, observed_rain_3d_mm: 26.7, observed_rain_7d_mm: 44.7, observed_rain_15d_mm: 48.3, source: "NASA GLC" },
  { district: "Kodagu", event_date: "2018-09-22", observed_slope_deg: 18.8, observed_elevation_m: 968.7, observed_rain_3d_mm: 0.0, observed_rain_7d_mm: 0.0, observed_rain_15d_mm: 32.5, source: "NASA GLC" },
  { district: "Kodagu", event_date: "2018-08-17", observed_slope_deg: 6.5, observed_elevation_m: 944.1, observed_rain_3d_mm: 131.3, observed_rain_7d_mm: 412.4, observed_rain_15d_mm: 594.7, source: "NASA GLC" },
  { district: "East Sikkim", event_date: "2007-09-07", observed_slope_deg: 36.0, observed_elevation_m: 383.0, observed_rain_3d_mm: 42.6, observed_rain_7d_mm: 93.0, observed_rain_15d_mm: 191.9, source: "NASA GLC" },
  { district: "East Sikkim", event_date: "2007-09-11", observed_slope_deg: 33.8, observed_elevation_m: 346.5, observed_rain_3d_mm: 130.5, observed_rain_7d_mm: 173.1, observed_rain_15d_mm: 256.1, source: "NASA GLC" },
  { district: "East Sikkim", event_date: "2010-08-26", observed_slope_deg: 11.2, observed_elevation_m: 360.6, observed_rain_3d_mm: 49.8, observed_rain_7d_mm: 118.6, observed_rain_15d_mm: 273.8, source: "NASA GLC" },
  { district: "West Sikkim", event_date: "2007-08-02", observed_slope_deg: 9.4, observed_elevation_m: 1594.4, observed_rain_3d_mm: 42.6, observed_rain_7d_mm: 106.4, observed_rain_15d_mm: 274.9, source: "NASA GLC" },
  { district: "West Sikkim", event_date: "2009-08-19", observed_slope_deg: 20.3, observed_elevation_m: 1281.2, observed_rain_3d_mm: 43.5, observed_rain_7d_mm: 58.0, observed_rain_15d_mm: 205.1, source: "NASA GLC" },
  { district: "West Sikkim", event_date: "2009-08-20", observed_slope_deg: 25.2, observed_elevation_m: 1226.4, observed_rain_3d_mm: 138.4, observed_rain_7d_mm: 185.2, observed_rain_15d_mm: 352.6, source: "NASA GLC" },
  { district: "East Khasi Hills", event_date: "2014-08-15", observed_slope_deg: 15.1, observed_elevation_m: 1835.6, observed_rain_3d_mm: 131.0, observed_rain_7d_mm: 131.0, observed_rain_15d_mm: 212.7, source: "NASA GLC" },
  { district: "East Khasi Hills", event_date: "2017-06-17", observed_slope_deg: 37.4, observed_elevation_m: 56.0, observed_rain_3d_mm: 165.3, observed_rain_7d_mm: 500.5, observed_rain_15d_mm: 672.1, source: "NASA GLC" },
  { district: "East Khasi Hills", event_date: "2017-06-17", observed_slope_deg: 4.9, observed_elevation_m: 1881.2, observed_rain_3d_mm: 120.0, observed_rain_7d_mm: 372.2, observed_rain_15d_mm: 488.8, source: "NASA GLC" }
];

async function loadAllObservations() {
  const districts = ["Wayanad", "Idukki", "Kodagu", "East Sikkim", "West Sikkim", "East Khasi Hills"];
  const allEvents = [];

  for (const dName of districts) {
    try {
      const safeName = dName.replace(/ /g, "_");
      let res = await fetch(`./data/districts/${encodeURIComponent(dName)}.json`);
      if (!res.ok) res = await fetch(`./data/districts/${safeName}.json`);
      if (res.ok) {
        const json = await res.json();
        if (json.historical_positive_events) {
          json.historical_positive_events.forEach((ev) => {
            allEvents.push({ ...ev, district: dName });
          });
        }
      }
    } catch (_) {}
  }

  // Fallback to verified catalog if local filesystem CORS blocked fetch
  if (allEvents.length === 0) {
    FALLBACK_OBSERVATIONS.forEach((ev) => allEvents.push(ev));
  }

  // Sort by event date descending
  allEvents.sort((a, b) => (b.event_date || "").localeCompare(a.event_date || ""));

  state.allObservations = allEvents;
  applyObservationFilters();
}

function filterObservations(district) {
  state.currentObsDistrictFilter = district;
  document.querySelectorAll(".btn-obs-pill").forEach((btn) => {
    if (btn.getAttribute("data-district") === district) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  applyObservationFilters();
}
window.filterObservations = filterObservations;

function handleObservationSearch() {
  const input = document.getElementById("obs-search-input");
  state.currentObsSearchQuery = (input ? input.value : "").toLowerCase().trim();
  applyObservationFilters();
}
window.handleObservationSearch = handleObservationSearch;

function applyObservationFilters() {
  let list = state.allObservations;
  if (state.currentObsDistrictFilter && state.currentObsDistrictFilter !== "all") {
    list = list.filter((ev) => ev.district === state.currentObsDistrictFilter);
  }
  if (state.currentObsSearchQuery) {
    const q = state.currentObsSearchQuery;
    list = list.filter((ev) => 
      (ev.district || "").toLowerCase().includes(q) ||
      (ev.event_date || "").toLowerCase().includes(q) ||
      String(ev.observed_slope_deg).includes(q) ||
      String(ev.observed_elevation_m).includes(q) ||
      String(ev.observed_rain_3d_mm).includes(q) ||
      String(ev.observed_rain_7d_mm).includes(q) ||
      String(ev.observed_rain_15d_mm).includes(q)
    );
  }
  state.filteredObservations = list;
  renderObservationsTable(list);
}

function renderObservationsTable(events) {
  const tbody = document.getElementById("tbody-all-observations");
  const countLabel = document.getElementById("obs-count-label");
  if (!tbody) return;

  if (countLabel) {
    countLabel.textContent = `Showing ${events.length} of ${state.allObservations.length} verified historical scenarios`;
  }

  if (events.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:18px; color:var(--text-muted);">No records found matching filter criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = events
    .map(
      (ev) => `
      <tr>
        <td><strong>${ev.district}</strong></td>
        <td>${ev.event_date}</td>
        <td>${ev.observed_slope_deg}&deg;</td>
        <td>${ev.observed_elevation_m} m</td>
        <td>${ev.observed_rain_3d_mm} mm</td>
        <td>${ev.observed_rain_7d_mm} mm</td>
        <td>${ev.observed_rain_15d_mm} mm</td>
        <td>
          <button class="btn-table-action" onclick="loadObsRecordIntoInference('${ev.district}', ${ev.observed_elevation_m}, ${ev.observed_slope_deg}, ${ev.observed_rain_3d_mm}, ${ev.observed_rain_7d_mm}, ${ev.observed_rain_15d_mm})">
            Load Scenario →
          </button>
        </td>
      </tr>
    `
    )
    .join("");
}

function loadObsRecordIntoInference(district, elev, slope, r3d, r7d, r15d) {
  selectDistrict(district);
  document.getElementById("inp-elev").value = elev;
  document.getElementById("inp-slope").value = slope;
  document.getElementById("inp-rain3d").value = r3d;
  document.getElementById("inp-rain7d").value = r7d;
  document.getElementById("inp-rain15d").value = r15d;

  navigateTo("inference");
  evaluateScenario();
}
window.loadObsRecordIntoInference = loadObsRecordIntoInference;

// ---------------------------------------------------------------------------
// Scenario Inference & Math Engine
// ---------------------------------------------------------------------------

function handleScenarioSubmit(e) {
  e.preventDefault();
  evaluateScenario();
}
window.handleScenarioSubmit = handleScenarioSubmit;

async function evaluateScenario() {
  const elev = parseFloat(document.getElementById("inp-elev").value);
  const slope = parseFloat(document.getElementById("inp-slope").value);
  const r3d = parseFloat(document.getElementById("inp-rain3d").value);
  const r7d = parseFloat(document.getElementById("inp-rain7d").value);
  const r15d = parseFloat(document.getElementById("inp-rain15d").value);

  const features = {
    elevation_m: elev,
    slope_deg: slope,
    rain_3d_mm: r3d,
    rain_7d_mm: r7d,
    rain_15d_mm: r15d,
    slope_max_1km: Math.min(75.0, slope * 1.25),
    slope_p90_1km: Math.min(70.0, slope * 1.15),
    elev_relief_1km: Math.max(50.0, elev * 0.25),
    slope_max_3km: Math.min(80.0, slope * 1.45),
    slope_p90_3km: Math.min(75.0, slope * 1.25),
    elev_relief_3km: Math.max(120.0, elev * 0.45),
    slope_max_5km: Math.min(85.0, slope * 1.65),
    slope_p90_5km: Math.min(78.0, slope * 1.35),
    elev_relief_5km: Math.max(200.0, elev * 0.65),
    rain_3km_mean_3d: r3d * 0.98,
    rain_3km_mean_7d: r7d * 0.98,
    rain_3km_mean_15d: r15d * 0.98,
  };

  const payload = {
    district: state.selectedDistrict,
    model_family: state.selectedModelFamily,
    feature_set: state.selectedFeatureSet,
    features: features,
  };

  try {
    let data = null;
    const isStaticHost =
      window.location.protocol === "file:" ||
      window.location.hostname.endsWith("github.io") ||
      window.location.hostname.endsWith("pages.dev");

    if (!isStaticHost) {
      try {
        const res = await fetch("/api/predict/rlsi", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) data = await res.json();
      } catch (_) {}
    }

    if (!data) {
      data = await evaluateScenarioClientSide(payload);
    }

    renderInferenceResult(data);
  } catch (err) {
    console.error("Evaluation error:", err);
  }
}
window.evaluateScenario = evaluateScenario;

async function evaluateScenarioClientSide(payload) {
  const { district, model_family, feature_set, features } = payload;
  const fold_id = DISTRICT_FOLD_MAP[district];
  if (!fold_id) throw new Error(`Unknown district: ${district}`);

  const modelKey = `${model_family}_${feature_set}_${fold_id}`;
  let modelData = modelCache.get(modelKey);
  if (!modelData) {
    const res = await fetch(`./data/models/${modelKey}.json`);
    if (!res.ok) throw new Error(`Model file not found: ${modelKey}`);
    modelData = await res.json();
    modelCache.set(modelKey, modelData);
  }

  const scaled = modelData.features.map((f, i) => {
    const val = features[f] !== undefined ? features[f] : 0.0;
    return (val - modelData.scaler_mean[i]) / modelData.scaler_scale[i];
  });

  let rlsi_score = 0.5;

  if (model_family === "LogisticRegression") {
    let z = modelData.intercept;
    for (let i = 0; i < scaled.length; i++) {
      z += modelData.coef[i] * scaled[i];
    }
    rlsi_score = 1.0 / (1.0 + Math.exp(-z));
  } else if (model_family === "RandomForest") {
    let treeSum = 0.0;
    for (const tree of modelData.trees) {
      let nodeIdx = 0;
      while (tree.children_left[nodeIdx] !== -1) {
        const featureIdx = tree.feature[nodeIdx];
        const threshold = tree.threshold[nodeIdx];
        if (scaled[featureIdx] <= threshold) {
          nodeIdx = tree.children_left[nodeIdx];
        } else {
          nodeIdx = tree.children_right[nodeIdx];
        }
      }
      treeSum += tree.value[nodeIdx];
    }
    rlsi_score = treeSum / modelData.trees.length;
  }

  const tau_star = modelData.tau_star;
  const exceeds = rlsi_score >= tau_star;

  let tier = "LOW";
  if (rlsi_score >= tau_star) {
    tier = "HIGH";
  } else if (rlsi_score >= 0.5 * tau_star) {
    tier = "ELEVATED";
  }

  const sop = SOP_GUIDANCE[tier];

  return {
    status: "success",
    district,
    model_family,
    feature_set,
    fold_id,
    rlsi_score: parseFloat(rlsi_score.toFixed(4)),
    decision_threshold: parseFloat(tau_star.toFixed(4)),
    exceeds_threshold: exceeds,
    category: sop.tier_name,
    category_description: exceeds
      ? "Terrain-rainfall conditions meet the operational threshold calibrated to detect historical landslide events in this spatial fold."
      : "Current scenario remains below the operational threshold for this district fold.",
    sop_guidance: {
      administrative_status: sop.administrative_status,
      community_actions: sop.community_actions,
      infrastructure_actions: sop.infrastructure_actions,
    },
  };
}

function renderInferenceResult(data) {
  const resultBox = document.getElementById("rlsi-result-box");
  const badge = document.getElementById("res-badge");
  const modelStamp = document.getElementById("res-model-stamp");
  const rlsiVal = document.getElementById("res-rlsi-score");
  const tauVal = document.getElementById("res-tau-star");
  const statusVal = document.getElementById("res-threshold-status");
  const descVal = document.getElementById("res-category-desc");
  const sopAdmin = document.getElementById("sop-admin-status");
  const sopComm = document.getElementById("sop-list-community");
  const sopInfra = document.getElementById("sop-list-infrastructure");

  resultBox.style.display = "block";
  badge.textContent = data.category;
  badge.className = `result-badge ${data.exceeds_threshold ? "high" : "low"}`;

  modelStamp.textContent = `${data.model_family} · ${data.feature_set} · ${data.fold_id}`;
  rlsiVal.textContent = data.rlsi_score.toFixed(4);
  tauVal.textContent = data.decision_threshold.toFixed(4);

  if (data.exceeds_threshold) {
    statusVal.textContent = "Exceeds Threshold";
    statusVal.style.color = "var(--accent-rose)";
  } else {
    statusVal.textContent = "Below Threshold (Safe)";
    statusVal.style.color = "var(--accent-emerald)";
  }

  descVal.textContent = data.category_description;

  const sop = data.sop_guidance || {};
  sopAdmin.textContent = `Administrative Status: ${sop.administrative_status || "Standard Standby"}`;

  sopComm.innerHTML = (sop.community_actions || []).map((a) => `<li>${a}</li>`).join("");
  sopInfra.innerHTML = (sop.infrastructure_actions || []).map((a) => `<li>${a}</li>`).join("");

  resultBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------------------------------------------------------------------------
// SHAP Feature Attribution Rendering (View 9)
// ---------------------------------------------------------------------------

function updateShapView() {
  const container = document.getElementById("shap-bars-container");
  if (!container || !state.explainabilityData) return;

  const exp = state.explainabilityData;
  const modelKey = state.selectedModelFamily === "LogisticRegression" ? "logistic_regression" : "random_forest";
  const modelInfo = exp[modelKey];

  if (!modelInfo || !modelInfo.top_features) {
    container.innerHTML = `<p style="color:var(--text-muted); font-size:12px;">No SHAP data available for this model.</p>`;
    return;
  }

  const features = modelInfo.top_features;
  const maxVal = Math.max(...features.map((f) => Math.abs(f.importance_score || f.mean_abs_shap || 0.1)));

  container.innerHTML = features
    .slice(0, 8)
    .map((f) => {
      const val = f.importance_score || f.mean_abs_shap || 0.05;
      const pct = Math.min(100, Math.max(10, Math.round((val / maxVal) * 100)));
      return `
      <div class="shap-bar-row">
        <div class="shap-meta">
          <span class="shap-feature-name">${f.feature_name}</span>
          <span class="shap-feature-val">${val.toFixed(4)}</span>
        </div>
        <div class="shap-bar-bg">
          <div class="shap-bar-fill" style="width: ${pct}%;"></div>
        </div>
      </div>
    `;
    })
    .join("");
}

// ---------------------------------------------------------------------------
// Interactive State-Space Hydrology Simulator (View 8)
// ---------------------------------------------------------------------------

function initSimulations() {
  updateStateSpaceSimulation();
}

const PRESET_RAINFALL = {
  cloudburst: [5, 8, 4, 10, 6, 8, 12, 15, 20, 25, 30, 45, 120, 40, 15],
  monsoon: [25, 35, 40, 50, 45, 60, 55, 70, 65, 80, 75, 90, 85, 95, 110],
  dryspell: [0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 45, 80, 95, 60, 25],
};

function applyStateSpacePreset() {
  const preset = document.getElementById("sim-preset").value;
  updateStateSpaceSimulation();
}
window.applyStateSpacePreset = applyStateSpacePreset;

function updateStateSpaceSimulation() {
  const lambdaEl = document.getElementById("sim-lambda");
  const lambdaValEl = document.getElementById("sim-lambda-val");
  const presetEl = document.getElementById("sim-preset");
  const chartEl = document.getElementById("statespace-chart-container");
  if (!lambdaEl || !chartEl) return;

  const lambda = parseFloat(lambdaEl.value);
  lambdaValEl.textContent = `λ = ${lambda.toFixed(2)} (Soil Retention Parameter)`;

  const presetKey = presetEl ? presetEl.value : "monsoon";
  const rainSeries = PRESET_RAINFALL[presetKey] || PRESET_RAINFALL.monsoon;

  // 1D Kalman DLM simulation: theta_t = lambda * theta_{t-1} + (1 - lambda) * P_t
  const theta = [];
  let currentTheta = 15.0; // initial baseline moisture

  for (let t = 0; t < rainSeries.length; t++) {
    const P_t = rainSeries[t];
    currentTheta = lambda * currentTheta + (1.0 - lambda) * P_t;
    theta.push(currentTheta);
  }

  const maxTheta = Math.max(...theta, 80);

  chartEl.innerHTML = theta
    .map((val, idx) => {
      const heightPct = Math.min(100, Math.max(12, Math.round((val / maxTheta) * 100)));
      const rain = rainSeries[idx];
      return `
      <div style="flex:1; display:flex; flex-direction:column; align-items:center; height:100%; justify-content:flex-end;" title="Day ${idx + 1}: Rain ${rain}mm, Saturation θ=${val.toFixed(1)}">
        <div style="font-size:9px; color:var(--text-dim); margin-bottom:2px;">${val.toFixed(0)}</div>
        <div style="width:100%; max-width:24px; height:${heightPct}%; background:linear-gradient(180deg, var(--accent-emerald), var(--accent-teal)); border-radius:3px 3px 0 0;"></div>
        <div style="font-size:9px; color:var(--text-muted); margin-top:4px;">D${idx + 1}</div>
      </div>
    `;
    })
    .join("");
}
window.updateStateSpaceSimulation = updateStateSpaceSimulation;

// ---------------------------------------------------------------------------
// Floating RAG Chatbot Controller
// ---------------------------------------------------------------------------

function toggleFloatingRAG() {
  const win = document.getElementById("floating-rag-window");
  if (win) {
    win.classList.toggle("open");
  }
}
window.toggleFloatingRAG = toggleFloatingRAG;

function openFloatingRAG() {
  const win = document.getElementById("floating-rag-window");
  if (win) {
    win.classList.add("open");
  }
}
window.openFloatingRAG = openFloatingRAG;
