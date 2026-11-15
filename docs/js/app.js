/**
 * LEWDSS Frontend Application Logic
 * Regional Landslide Early Warning & Emergency Response Decision Support System
 * 
 * Provides:
 * - Dynamic district selection and profile rendering.
 * - Historical NASA GLC catalog event browsing and scenario loading.
 * - Dual-mode scenario evaluation: live REST API when available, or instant
 *   client-side mathematical inference when hosted statically (e.g., GitHub Pages).
 * - Project-defined RLSI categorization and NDMA-aligned SOP guidance display.
 * - SHAP feature attribution visualization with attribution-vs-causation boundaries.
 */

// Application State
const state = {
  selectedDistrict: "Wayanad",
  selectedModelFamily: "LogisticRegression",
  selectedFeatureSet: "FS3_Full",
  districtData: null,
  explainabilityData: null,
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

// NDMA-aligned Standard Operating Procedures guidance
const SOP_GUIDANCE = {
  LOW: {
    tier_name: "Low Relative Susceptibility",
    badge_color: "green",
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
    emergency_desk_checklist: [
      "Standard monitoring of daily Indian Meteorological Department (IMD) district rainfall bulletins.",
      "Maintain baseline inventory of emergency machinery (excavators, backhoes) at taluk headquarters.",
    ],
  },
  ELEVATED: {
    tier_name: "Elevated Relative Susceptibility",
    badge_color: "amber",
    administrative_status: "Heightened Vigilance & Advisory Mode",
    community_actions: [
      "Advise residents living near steep, modified, or previously failed slopes to monitor for fresh ground cracks.",
      "Avoid non-essential nighttime travel along steep mountain roads during periods of continuous rainfall.",
      "Ensure household emergency battery packs, flashlights, and mobile communications remain charged.",
      "Identify nearest designated community relief shelters and primary evacuation walking routes.",
    ],
    infrastructure_actions: [
      "Deploy road maintenance inspection teams along vulnerable highway stretches with known chronic slide history.",
      "Verify that earthmoving equipment and operators are on stand-by at taluk public works depots.",
      "Install temporary cautionary signage along identified steep cuttings with loose boulders or saturated soils.",
    ],
    emergency_desk_checklist: [
      "Track 24-hour and 72-hour rainfall accumulation against regional historical flash flood/landslide averages.",
      "Establish active communication check-ins between District Emergency Operations Centre (DEOC) and taluk tehsildars.",
      "Verify satellite phone communication readiness for remote hillside villages vulnerable to road cutoffs.",
    ],
  },
  HIGH: {
    tier_name: "High Relative Susceptibility",
    badge_color: "red",
    administrative_status: "Preparedness Advisory & Resource Standby",
    community_actions: [
      "Review family emergency communication plan and keep essential medications, identity documents, and emergency bags accessible.",
      "Heed official notifications from District Collector / DDMA regarding potential localized precautionary relocation.",
      "Immediately report rapid water color changes (sudden mud surges in clear mountain streams) or ground rumbling to local authorities.",
      "Stay clear of river channels and steep ravines susceptible to debris flows during intense cloudbursts.",
    ],
    infrastructure_actions: [
      "Position heavy earthmoving equipment and debris clearance squads at strategic junctions along critical arterial highways.",
      "Coordinate with Traffic Police for possible restricted/regulated heavy-vehicle movement on vulnerable ghat routes.",
      "Inspect bridge abutments and mountain stream crossings for debris damming or backwater accumulation.",
    ],
    emergency_desk_checklist: [
      "Activate emergency relief centers / relief camps in secure, low-hazard taluk school buildings or auditoriums.",
      "Coordinate inter-agency stand-by status with National Disaster Response Force (NDRF) / State Disaster Response Force (SDRF).",
      "Prepare official advisory bulletins for dissemination through DDMA authorized public broadcast channels.",
    ],
  },
};

const INSTITUTIONAL_DISCLAIMER =
  "Institutional Disclaimer: All emergency advisories are governed strictly by the District Disaster Management Authority (DDMA). LEWDSS does not issue evacuation orders.";

// In-memory cache for client-side model parameter files
const modelCache = new Map();

// DOM Element References
const dom = {
  districtButtons: document.querySelectorAll(".btn-district"),
  selectModel: document.getElementById("select-model-family"),
  selectFeatureSet: document.getElementById("select-feature-set"),

  // Header Stats
  regionBadge: document.getElementById("district-region-badge"),
  districtTitle: document.getElementById("district-title"),
  districtFoldInfo: document.getElementById("district-fold-info"),
  statElev: document.getElementById("stat-elev"),
  statPos: document.getElementById("stat-pos"),
  statDates: document.getElementById("stat-dates"),
  statRecall: document.getElementById("stat-recall"),

  // Historical Table
  tbodyEvents: document.getElementById("tbody-historical-events"),

  // Scenario Form & Inputs
  formScenario: document.getElementById("form-rlsi-scenario"),
  inpElev: document.getElementById("inp-elev"),
  inpSlope: document.getElementById("inp-slope"),
  inpRain3d: document.getElementById("inp-rain3d"),
  inpRain7d: document.getElementById("inp-rain7d"),
  inpRain15d: document.getElementById("inp-rain15d"),
  btnReset: document.getElementById("btn-reset-scenario"),

  // Results Elements
  resultBox: document.getElementById("rlsi-result-box"),
  resBadge: document.getElementById("res-badge"),
  resModelStamp: document.getElementById("res-model-stamp"),
  resRlsiScore: document.getElementById("res-rlsi-score"),
  resTauStar: document.getElementById("res-tau-star"),
  resThresholdStatus: document.getElementById("res-threshold-status"),
  resCategoryDesc: document.getElementById("res-category-desc"),

  // SOP Guidance
  sopAdminStatus: document.getElementById("sop-admin-status"),
  sopListCommunity: document.getElementById("sop-list-community"),
  sopListInfrastructure: document.getElementById("sop-list-infrastructure"),
  sopDisclaimer: document.getElementById("sop-disclaimer-text"),

  // SHAP Container
  shapBarsContainer: document.getElementById("shap-bars-container"),
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadDistrict(state.selectedDistrict);
});

function setupEventListeners() {
  // District Switchers
  dom.districtButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      dom.districtButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const dName = btn.getAttribute("data-district");
      state.selectedDistrict = dName;
      loadDistrict(dName);
    });
  });

  // Model and Feature Set Configuration
  dom.selectModel.addEventListener("change", (e) => {
    state.selectedModelFamily = e.target.value;
    updateShapView();
    updateRecallStat();
  });

  dom.selectFeatureSet.addEventListener("change", (e) => {
    state.selectedFeatureSet = e.target.value;
    updateRecallStat();
  });

  // Scenario Form Submit
  dom.formScenario.addEventListener("submit", (e) => {
    e.preventDefault();
    evaluateScenario();
  });

  // Reset Button
  dom.btnReset.addEventListener("click", () => {
    resetScenarioToDistrictMedian();
  });
}

// ---------------------------------------------------------------------------
// Data Fetching & District Loading (Hybrid: API + Static Fallback)
// ---------------------------------------------------------------------------

async function loadDistrict(districtName) {
  try {
    let distData = null;
    let expData = null;

    // Detect if running statically (e.g., GitHub Pages, local file, or without backend)
    const isStaticHost =
      window.location.protocol === "file:" ||
      window.location.hostname.endsWith("github.io") ||
      window.location.hostname.endsWith("pages.dev");

    // Try API first if not strictly on a static host
    if (!isStaticHost) {
      try {
        const distRes = await fetch(`/api/districts/${encodeURIComponent(districtName)}`);
        if (distRes.ok) distData = await distRes.json();
      } catch (_) {
        // Fall back to static
      }
    }

    // Static fallback
    if (!distData) {
      const safeName = districtName.replace(/ /g, "_");
      let res = await fetch(`./data/districts/${encodeURIComponent(districtName)}.json`);
      if (!res.ok) {
        res = await fetch(`./data/districts/${safeName}.json`);
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      distData = await res.json();
    }

    state.districtData = distData;
    renderDistrictOverview();
    renderHistoricalEventsTable();

    // 2. Fetch explainability SHAP attributions
    if (!isStaticHost) {
      try {
        const expRes = await fetch(`/api/explainability/${encodeURIComponent(districtName)}`);
        if (expRes.ok) expData = await expRes.json();
      } catch (_) {
        // Fall back to static
      }
    }

    if (!expData) {
      const safeName = districtName.replace(/ /g, "_");
      let expRes = await fetch(`./data/explainability/${encodeURIComponent(districtName)}.json`);
      if (!expRes.ok) {
        expRes = await fetch(`./data/explainability/${safeName}.json`);
      }
      if (expRes.ok) expData = await expRes.json();
    }

    if (expData) {
      state.explainabilityData = expData;
      updateShapView();
    }

    // 3. Reset scenario inputs
    resetScenarioToDistrictMedian();
  } catch (err) {
    console.error("Failed loading district data:", err);
    dom.tbodyEvents.innerHTML = `<tr><td colspan="5" class="loading-cell" style="color:#cf222e;">Failed loading district data: ${err.message}.</td></tr>`;
  }
}

// ---------------------------------------------------------------------------
// Rendering Functions
// ---------------------------------------------------------------------------

function renderDistrictOverview() {
  const d = state.districtData;
  if (!d) return;

  dom.regionBadge.textContent = d.region;
  dom.districtTitle.textContent = `${d.district} District, ${d.state}`;
  dom.districtFoldInfo.textContent = `Spatial Validation Fold: ${d.primary_fold} · Trained on: ${d.train_districts.join(", ")}`;

  const topo = d.topographic_profile || {};
  dom.statElev.textContent = `${topo.elevation_min_m || 0} m – ${topo.elevation_max_m || 0} m`;
  dom.statPos.textContent = `${d.n_historical_events} documented events`;

  // Catalog dates span
  if (d.historical_positive_events && d.historical_positive_events.length > 0) {
    const dates = d.historical_positive_events.map((e) => e.event_date).sort();
    const startYear = dates[0].substring(0, 4);
    const endYear = dates[dates.length - 1].substring(0, 4);
    dom.statDates.textContent = `${startYear} – ${endYear}`;
  } else {
    dom.statDates.textContent = "N/A";
  }

  updateRecallStat();
}

function updateRecallStat() {
  const d = state.districtData;
  if (!d || !d.audited_fold_metrics) return;

  const key = `${state.selectedModelFamily}_${state.selectedFeatureSet}`;
  const metrics = d.audited_fold_metrics[key];
  if (metrics) {
    const recallPct = (metrics.recall * 100).toFixed(1);
    const tp = metrics.tp;
    const totalPos = metrics.tp + metrics.fn;
    dom.statRecall.textContent = `${recallPct}% (${tp}/${totalPos})`;
    if (metrics.target_recall_met) {
      dom.statRecall.style.color = "var(--color-primary)";
    } else {
      dom.statRecall.style.color = "var(--color-hazard-high)";
    }
  } else {
    dom.statRecall.textContent = "Audited in Fold";
  }
}

function renderHistoricalEventsTable() {
  const d = state.districtData;
  if (!d || !d.historical_positive_events) return;

  const events = d.historical_positive_events;
  if (events.length === 0) {
    dom.tbodyEvents.innerHTML = `<tr><td colspan="5" class="loading-cell">No documented historical events in this district.</td></tr>`;
    return;
  }

  let html = "";
  events.forEach((ev, idx) => {
    html += `
      <tr data-idx="${idx}">
        <td><strong>${ev.event_date}</strong><br><small style="color:var(--color-text-muted);">${ev.event_id}</small></td>
        <td><code>${ev.observed_rain_3d_mm} / ${ev.observed_rain_7d_mm} / ${ev.observed_rain_15d_mm} mm</code></td>
        <td>${ev.observed_slope_deg}&deg;</td>
        <td>${ev.observed_elevation_m} m</td>
        <td>
          <button type="button" class="btn-table-action" onclick="loadEventIntoScenario(${idx})">Load Scenario</button>
        </td>
      </tr>
    `;
  });

  dom.tbodyEvents.innerHTML = html;
}

// Global hook for row button
window.loadEventIntoScenario = function (idx) {
  const d = state.districtData;
  if (!d || !d.historical_positive_events) return;
  const ev = d.historical_positive_events[idx];
  if (!ev) return;

  dom.inpElev.value = ev.observed_elevation_m;
  dom.inpSlope.value = ev.observed_slope_deg;
  dom.inpRain3d.value = ev.observed_rain_3d_mm;
  dom.inpRain7d.value = ev.observed_rain_7d_mm;
  dom.inpRain15d.value = ev.observed_rain_15d_mm;

  // Highlight selected table row
  const rows = dom.tbodyEvents.querySelectorAll("tr");
  rows.forEach((r) => r.classList.remove("selected"));
  if (rows[idx]) rows[idx].classList.add("selected");

  // Automatically trigger evaluation for convenient inspection
  evaluateScenario();
};

function resetScenarioToDistrictMedian() {
  const d = state.districtData;
  if (!d) return;

  const topo = d.topographic_profile || {};
  dom.inpElev.value = topo.elevation_mean_m || 1000;
  dom.inpSlope.value = topo.slope_mean_deg || 20;

  // If historical events exist, use median rainfall, else baseline
  if (d.historical_positive_events && d.historical_positive_events.length > 0) {
    const midIdx = Math.floor(d.historical_positive_events.length / 2);
    const midEv = d.historical_positive_events[midIdx];
    dom.inpRain3d.value = midEv.observed_rain_3d_mm;
    dom.inpRain7d.value = midEv.observed_rain_7d_mm;
    dom.inpRain15d.value = midEv.observed_rain_15d_mm;
  } else {
    dom.inpRain3d.value = 50.0;
    dom.inpRain7d.value = 120.0;
    dom.inpRain15d.value = 220.0;
  }

  // Clear row highlights
  const rows = dom.tbodyEvents.querySelectorAll("tr");
  rows.forEach((r) => r.classList.remove("selected"));
}

// ---------------------------------------------------------------------------
// Scenario Evaluation (Dual Mode: REST API + Client-Side Math Engine)
// ---------------------------------------------------------------------------

async function evaluateScenario() {
  const elev = parseFloat(dom.inpElev.value);
  const slope = parseFloat(dom.inpSlope.value);
  const r3d = parseFloat(dom.inpRain3d.value);
  const r7d = parseFloat(dom.inpRain7d.value);
  const r15d = parseFloat(dom.inpRain15d.value);

  // Construct full 17 feature dictionary
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

    // 1. If not strictly static, try live API server
    if (!isStaticHost) {
      try {
        const res = await fetch("/api/predict/rlsi", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          data = await res.json();
        }
      } catch (_) {
        // Fall back to client-side mathematical evaluation
      }
    }

    // 2. Client-side evaluation engine (runs on GitHub Pages without any backend server)
    if (!data) {
      data = await evaluateScenarioClientSide(payload);
    }

    renderRlsiResult(data);
  } catch (err) {
    alert(`Scenario evaluation error: ${err.message}`);
  }
}

/**
 * Pure client-side model inference engine matching Python scikit-learn models.
 * Operates with 100% mathematical fidelity on frozen checkpoint parameters.
 */
async function evaluateScenarioClientSide(payload) {
  const { district, model_family, feature_set, features } = payload;
  const fold_id = DISTRICT_FOLD_MAP[district];
  if (!fold_id) throw new Error(`Unknown district: ${district}`);

  const modelKey = `${model_family}_${feature_set}_${fold_id}`;
  let modelData = modelCache.get(modelKey);
  if (!modelData) {
    const res = await fetch(`./data/models/${modelKey}.json`);
    if (!res.ok) {
      throw new Error(`Failed to load model file (${res.status})`);
    }
    modelData = await res.json();
    modelCache.set(modelKey, modelData);
  }

  // Feature vector in exact schema order & StandardScaler transformation
  const scaled = modelData.features.map((f, i) => {
    const val = features[f] !== undefined ? features[f] : 0.0;
    return (val - modelData.scaler_mean[i]) / modelData.scaler_scale[i];
  });

  let rlsi_score = 0.5;

  if (model_family === "LogisticRegression") {
    // Linear predictor z = w0 + sum(wi * xi)
    let z = modelData.intercept;
    for (let i = 0; i < scaled.length; i++) {
      z += modelData.coef[i] * scaled[i];
    }
    // Sigmoid probability
    rlsi_score = 1.0 / (1.0 + Math.exp(-z));
  } else if (model_family === "RandomForest") {
    // Ensemble tree traversal
    let treeSum = 0.0;
    for (const tree of modelData.trees) {
      let node = 0;
      while (tree.left[node] !== -1) {
        const featIdx = tree.feature[node];
        const thresh = tree.threshold[node];
        if (scaled[featIdx] <= thresh) {
          node = tree.left[node];
        } else {
          node = tree.right[node];
        }
      }
      treeSum += tree.prob[node];
    }
    rlsi_score = treeSum / modelData.trees.length;
  }

  // Frozen operational decision threshold
  const tau_star = modelData.tau_star;
  let category_name = "";
  let category_code = "";
  let category_desc = "";

  if (rlsi_score >= tau_star) {
    category_name = "High Relative Susceptibility";
    category_code = "HIGH";
    category_desc = `Score (${rlsi_score.toFixed(3)}) meets or exceeds the empirical decision threshold (tau* = ${tau_star.toFixed(3)}). Terrain and antecedent precipitation reflect conditions associated with historical landslide events.`;
  } else if (rlsi_score >= 0.5 * tau_star) {
    category_name = "Elevated Relative Susceptibility";
    category_code = "ELEVATED";
    category_desc = `Score (${rlsi_score.toFixed(3)}) is between 50% of threshold and threshold (0.5*tau* = ${(0.5 * tau_star).toFixed(3)}, tau* = ${tau_star.toFixed(3)}). Conditions are elevated relative to median landscape background; heightened monitoring recommended.`;
  } else {
    category_name = "Low Relative Susceptibility";
    category_code = "LOW";
    category_desc = `Score (${rlsi_score.toFixed(3)}) is below 50% of threshold (0.5*tau* = ${(0.5 * tau_star).toFixed(3)}). Conditions are within the baseline regional landscape background envelope.`;
  }

  const sop = SOP_GUIDANCE[category_code] || SOP_GUIDANCE.LOW;

  return {
    rlsi_score: parseFloat(rlsi_score.toFixed(4)),
    frozen_threshold_tau: parseFloat(tau_star.toFixed(4)),
    exceeds_threshold: rlsi_score >= tau_star,
    category: category_name,
    category_code: category_code,
    category_description: category_desc,
    model_family: model_family,
    feature_set: feature_set,
    fold_id: fold_id,
    sop_preparedness_guidance: {
      category_code: category_code,
      tier_name: sop.tier_name,
      badge_color: sop.badge_color,
      administrative_status: sop.administrative_status,
      community_actions: [...sop.community_actions],
      infrastructure_actions: [...sop.infrastructure_actions],
      emergency_desk_checklist: [...sop.emergency_desk_checklist],
      institutional_disclaimer: INSTITUTIONAL_DISCLAIMER,
    },
  };
}

function renderRlsiResult(data) {
  dom.resultBox.style.display = "block";
  dom.resModelStamp.textContent = `${data.model_family} · ${data.feature_set} · ${data.fold_id}`;
  dom.resRlsiScore.textContent = data.rlsi_score.toFixed(4);
  dom.resTauStar.textContent = data.frozen_threshold_tau.toFixed(4);

  // Badge Styling
  dom.resBadge.textContent = data.category;
  dom.resBadge.className = "result-badge";
  if (data.category_code === "HIGH") {
    dom.resBadge.classList.add("badge-high");
    dom.resThresholdStatus.textContent = "Exceeds Decision Threshold (RLSI ≥ τ*)";
    dom.resThresholdStatus.className = "sm-value threshold-met";
  } else if (data.category_code === "ELEVATED") {
    dom.resBadge.classList.add("badge-elevated");
    dom.resThresholdStatus.textContent = "Elevated Range (0.5τ* ≤ RLSI < τ*)";
    dom.resThresholdStatus.className = "sm-value";
    dom.resThresholdStatus.style.color = "var(--color-hazard-elevated)";
  } else {
    dom.resBadge.classList.add("badge-low");
    dom.resThresholdStatus.textContent = "Within Background (RLSI < 0.5τ*)";
    dom.resThresholdStatus.className = "sm-value threshold-unmet";
  }

  dom.resCategoryDesc.textContent = data.category_description;

  // Render SOP Preparedness Guidance
  const sop = data.sop_preparedness_guidance;
  if (sop) {
    dom.sopAdminStatus.textContent = `Administrative Status: ${sop.administrative_status}`;
    dom.sopListCommunity.innerHTML = sop.community_actions.map((a) => `<li>${a}</li>`).join("");
    dom.sopListInfrastructure.innerHTML = sop.infrastructure_actions.map((a) => `<li>${a}</li>`).join("");
    dom.sopDisclaimer.textContent = sop.institutional_disclaimer;
  }

  // Scroll smoothly to results
  dom.resultBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------------------------------------------------------------------------
// SHAP Explainability View
// ---------------------------------------------------------------------------

function updateShapView() {
  const exp = state.explainabilityData;
  if (!exp || !exp.analyses) return;

  // Find analysis matching selected model family (prefer FS3_Full, fallback to FS1_Point)
  let matchingAnalysis = exp.analyses.find(
    (a) => a.model_family === state.selectedModelFamily && a.feature_set === "FS3_Full"
  );
  if (!matchingAnalysis) {
    matchingAnalysis = exp.analyses.find(
      (a) => a.model_family === state.selectedModelFamily
    );
  }

  if (!matchingAnalysis || !matchingAnalysis.feature_attribution_ranking) {
    dom.shapBarsContainer.innerHTML = `<p class="loading-cell">No SHAP attribution found for ${state.selectedModelFamily}.</p>`;
    return;
  }

  const ranking = matchingAnalysis.feature_attribution_ranking.slice(0, 6);
  const maxVal = Math.max(...ranking.map((r) => r.mean_abs_shap), 0.001);

  let html = "";
  ranking.forEach((r) => {
    const pct = ((r.mean_abs_shap / maxVal) * 100).toFixed(1);
    html += `
      <div class="shap-row">
        <span class="shap-feat-name" title="${r.feature}">${r.feature}</span>
        <div class="shap-bar-track">
          <div class="shap-bar-fill" style="width: ${pct}%;"></div>
        </div>
        <span class="shap-val-text">${r.mean_abs_shap.toFixed(3)}</span>
      </div>
    `;
  });

  dom.shapBarsContainer.innerHTML = html;
}
