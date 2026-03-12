/*
 * ============================================================================
 * Credit Risk ML Dashboard — APEX Application Setup Guide
 * ============================================================================
 *
 * DEPLOYED DASHBOARD (LIVE):
 *   https://G95D3985BD0D2FD-PODACADEMY2.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/dashboard/
 *
 *   The dashboard is served via ORDS REST from the ADW database.
 *   Source HTML: dashboard.html (self-contained, Chart.js, dark theme)
 *   Upload script: upload_dashboard.py
 *
 * APEX BUILDER ACCESS:
 *   URL:       https://G95D3985BD0D2FD-PODACADEMY2.adb.sa-saopaulo-1.oraclecloudapps.com/ords/apex
 *   Workspace: MLMONITOR
 *   Username:  DASHADMIN
 *   Password:  CreditRisk2026#ML
 *
 * PRE-REQUISITES (already executed):
 *   - 01_create_schema.sql (MLMONITOR user + APEX workspace)
 *   - 02_create_tables.sql (7 tables + 4 views)
 *   - 03_seed_data.sql (real project metrics)
 *
 * ============================================================================
 * STEP 1: Create Application (APEX Builder)
 * ============================================================================
 *
 * 1. Log in to APEX Builder
 * 2. Click "App Builder" > "Create"
 * 3. Select "New Application"
 * 4. Settings:
 *    - Name: Credit Risk ML Dashboard
 *    - Application ID: 100
 *    - Appearance > Theme Style: Vita - Dark
 *    - Features: Check "About Page"
 * 5. Add Pages:
 *    - Page 1: Dashboard (default home page)
 *    - Add Page > Blank Page: "Model Performance"
 *    - Add Page > Blank Page: "Operations & Costs"
 * 6. Click "Create Application"
 *
 * ============================================================================
 * STEP 2: Configure Page 1 — Executive Overview Dashboard
 * ============================================================================
 *
 * After app creation, open Page 1 in Page Designer.
 * Add the following regions (right-click Body > Create Region):
 *
 * --- REGION 1: Model Status Cards (Static Content) ---
 * Title: Model Health
 * Type: Static Content
 * Template: Hero
 * Source > HTML:
 */

-- Region 1 HTML (copy to Static Content source):
/*
<div style="display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; padding: 10px;">

  <div style="background: linear-gradient(135deg, #1a7f37 0%, #2ea043 100%); border-radius: 16px; padding: 24px 32px; min-width: 200px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">Status</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">STABLE</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Quality Gate: PASSED</div>
  </div>

  <div style="background: linear-gradient(135deg, #0d419d 0%, #1f6feb 100%); border-radius: 16px; padding: 24px 32px; min-width: 200px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">KS (OOT)</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">35.01%</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Ensemble Top-3 Average</div>
  </div>

  <div style="background: linear-gradient(135deg, #0d419d 0%, #1f6feb 100%); border-radius: 16px; padding: 24px 32px; min-width: 200px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">AUC-ROC</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">0.7368</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Ensemble Top-3 Average</div>
  </div>

  <div style="background: linear-gradient(135deg, #0d419d 0%, #1f6feb 100%); border-radius: 16px; padding: 24px 32px; min-width: 200px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">Gini</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">47.35%</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Ensemble Top-3 Average</div>
  </div>

  <div style="background: linear-gradient(135deg, #1a7f37 0%, #2ea043 100%); border-radius: 16px; padding: 24px 32px; min-width: 200px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">PSI (Score)</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">0.0008</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Estavel - Sem Drift</div>
  </div>

  <div style="background: linear-gradient(135deg, #6e40c9 0%, #8957e5 100%); border-radius: 16px; padding: 24px 32px; min-width: 200px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">Volume</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">3.9M</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Records Scored</div>
  </div>

</div>
*/

-- ============================================================================
-- Region 2: KS Evolution by SAFRA (Line Chart)
-- ============================================================================
-- Type: Chart
-- Chart Type: Line
-- SQL Source:

SELECT safra AS label,
       ks_statistic * 100 AS value,
       model_name AS series
FROM model_performance
WHERE dataset_type IN ('OOS','OOT','TRAIN')
ORDER BY safra, model_name;

-- Chart Settings:
--   Axis > Label: SAFRA | Value: KS (%)
--   Series Colors: Ensemble_Average=#1f6feb, CatBoost=#f97316, LightGBM_v2=#2ea043, XGBoost=#8957e5, LR_L1_v2=#d29922, RF=#da3633
--   Title: KS Statistic Evolution by SAFRA

-- ============================================================================
-- Region 3: PSI Stability Trend (Line + Area Chart)
-- ============================================================================
-- Type: Chart
-- Chart Type: Line with Area
-- SQL Source:

SELECT safra AS label,
       score_psi AS value,
       model_name AS series
FROM score_stability
ORDER BY safra, model_name;

-- Chart Settings:
--   Axis > Value: PSI
--   Series Colors: Ensemble_Average=#1f6feb, CatBoost=#f97316, LightGBM_v2=#2ea043, XGBoost=#8957e5
--   Reference Lines:
--     y=0.10 (dashed yellow, label "WARNING")
--     y=0.25 (dashed red, label "RETRAIN")
--   Title: Score PSI Stability Trend (4 models)

-- ============================================================================
-- Region 4: Risk Band Distribution (Stacked Bar Chart)
-- ============================================================================
-- Type: Chart
-- Chart Type: Bar (Stacked)
-- SQL Source:

-- Ensemble_Average view (default)
SELECT safra AS label,
       pct_critico AS "Critico (0-299)",
       pct_alto AS "Alto (300-499)",
       pct_medio AS "Medio (500-699)",
       pct_baixo AS "Baixo (700-1000)"
FROM score_distribution
WHERE model_name = 'Ensemble_Average'
ORDER BY safra;

-- CatBoost view (switch via interactive actions or separate region)
-- SELECT safra AS label, pct_critico, pct_alto, pct_medio, pct_baixo
-- FROM score_distribution WHERE model_name = 'CatBoost' ORDER BY safra;

-- Chart Settings:
--   Stack: Yes
--   Colors: Critico=#da3633, Alto=#f97316, Medio=#d29922, Baixo=#1a7f37
--   Value Format: #.0%
--   Title: Risk Band Distribution by SAFRA

-- ============================================================================
-- Region 5: Model Comparison Table (Classic Report)
-- ============================================================================
-- Type: Classic Report
-- SQL Source:

SELECT p.safra AS "SAFRA",
       p.dataset_type AS "Dataset",
       p.model_name AS "Model",
       ROUND(p.ks_statistic * 100, 2) || '%' AS "KS",
       ROUND(p.auc_roc, 4) AS "AUC",
       ROUND(p.gini, 2) || '%' AS "Gini",
       TO_CHAR(p.n_records, '999,999,999') AS "Records"
FROM model_performance p
WHERE p.model_name IN ('Ensemble_Average', 'CatBoost', 'LightGBM_v2', 'XGBoost')
ORDER BY p.safra, DECODE(p.model_name, 'Ensemble_Average', 1, 'CatBoost', 2, 'LightGBM_v2', 3, 'XGBoost', 4);

-- Report Settings:
--   Template: Standard
--   Highlight: model_name = 'CatBoost' > Orange row
--   Title: Model Performance Comparison (Ensemble + Top 3)

-- ============================================================================
-- STEP 3: Configure Page 2 — Model Performance Deep Dive
-- ============================================================================

-- ============================================================================
-- Region 6: AUC-ROC Evolution (Line Chart)
-- ============================================================================
-- Type: Chart
-- Chart Type: Line
-- SQL Source:

SELECT safra AS label,
       auc_roc AS value,
       model_name AS series
FROM model_performance
ORDER BY safra, model_name;

-- Chart Settings:
--   Axis > Value: AUC-ROC (0 to 1)
--   Colors: Ensemble_Average=#1f6feb, CatBoost=#f97316, LightGBM_v2=#2ea043, XGBoost=#8957e5
--   Title: AUC-ROC Evolution

-- ============================================================================
-- Region 7: Gini Coefficient Trend (Line Chart)
-- ============================================================================
-- Type: Chart
-- Chart Type: Line
-- SQL Source:

SELECT safra AS label,
       gini AS value,
       model_name AS series
FROM model_performance
ORDER BY safra, model_name;

-- Chart Settings:
--   Axis > Value: Gini (%)
--   Title: Gini Coefficient Trend

-- ============================================================================
-- Region 8: Feature Drift Heatmap (Classic Report with Conditional Formatting)
-- ============================================================================
-- Type: Classic Report
-- SQL Source:

-- Ensemble view (default) + CatBoost (toggle via model_name filter)
SELECT model_name AS "Model",
       feature_name AS "Feature",
       safra AS "SAFRA",
       ROUND(feature_psi, 4) AS "PSI",
       drift_status AS "Status",
       ROUND(train_mean, 2) AS "Train Mean",
       ROUND(oot_mean, 2) AS "OOT Mean",
       ROUND(ABS(oot_mean - train_mean) / NULLIF(train_std, 0) * 100, 1) || '%' AS "Shift %"
FROM feature_drift
WHERE model_name IN ('Ensemble_Average', 'CatBoost')
ORDER BY model_name, safra DESC, feature_psi DESC;

-- Report Settings:
--   Column "Status" > Column Formatting > CSS Classes:
--     if value = 'GREEN': u-success
--     if value = 'YELLOW': u-warning
--     if value = 'RED': u-danger
--   Highlight: model_name = 'CatBoost' > Orange row
--   Title: Feature Drift Analysis — Ensemble vs CatBoost (Top 20 Features)

-- ============================================================================
-- Region 9: Drift Summary by SAFRA (Bar Chart)
-- ============================================================================
-- Type: Chart
-- Chart Type: Bar (Stacked)
-- SQL Source:

SELECT model_name || ' — ' || safra AS label,
       features_ok AS "OK",
       features_warning AS "Warning",
       features_retrain AS "Retrain"
FROM v_drift_summary
WHERE model_name IN ('Ensemble_Average', 'CatBoost')
ORDER BY model_name, safra;

-- Chart Settings:
--   Stack: Yes
--   Colors: OK=#1a7f37, Warning=#d29922, Retrain=#da3633
--   Title: Feature Drift Summary by SAFRA

-- ============================================================================
-- Region 10: Score Distribution Statistics (Classic Report)
-- ============================================================================
-- Type: Classic Report
-- SQL Source:

SELECT model_name AS "Model",
       safra AS "SAFRA",
       score_mean AS "Mean",
       score_median AS "Median",
       score_p25 AS "P25",
       score_p75 AS "P75",
       score_std AS "Std Dev",
       TO_CHAR(total_scored, '999,999,999') AS "Volume"
FROM score_distribution
WHERE model_name IN ('Ensemble_Average', 'CatBoost')
ORDER BY model_name, safra;

-- Report Settings:
--   Title: Score Distribution by SAFRA — Ensemble vs CatBoost

-- ============================================================================
-- STEP 4: Configure Page 3 — Operations & Costs
-- ============================================================================

-- ============================================================================
-- Region 11: Pipeline Execution History (Interactive Report)
-- ============================================================================
-- Type: Interactive Report
-- SQL Source:

SELECT stage AS "Stage",
       status AS "Status",
       TO_CHAR(started_at, 'DD/MM/YYYY HH24:MI') AS "Started",
       TO_CHAR(finished_at, 'DD/MM/YYYY HH24:MI') AS "Finished",
       duration_sec || 's' AS "Duration",
       TO_CHAR(records_in, '999,999,999') AS "Records In",
       TO_CHAR(records_out, '999,999,999') AS "Records Out",
       notes AS "Notes"
FROM pipeline_runs
ORDER BY started_at DESC;

-- Report Settings:
--   Highlight Rule: Status = 'SUCCESS' > Green background
--   Highlight Rule: Status = 'FAILED' > Red background
--   Title: Pipeline Execution History

-- ============================================================================
-- Region 12: Cost Breakdown (Donut Chart)
-- ============================================================================
-- Type: Chart
-- Chart Type: Donut/Pie
-- SQL Source:

SELECT service_name AS label,
       cost_brl AS value
FROM cost_tracking
WHERE period = '2026-03'
ORDER BY cost_brl DESC;

-- Chart Settings:
--   Colors: Orchestrator=#1f6feb, Object Storage=#8957e5, Data Flow=#f97316
--   Value Format: R$ #,##0.00
--   Title: Cost Breakdown — Mar 2026 (R$ 168.00 of R$ 500 trial)

-- ============================================================================
-- Region 13: Cost Trend (Bar Chart)
-- ============================================================================
-- Type: Chart
-- Chart Type: Bar (Stacked)
-- SQL Source:

SELECT period AS label,
       total_cost AS "Total",
       orchestrator_cost AS "Orchestrator",
       dataflow_cost AS "Data Flow",
       storage_cost AS "Storage"
FROM v_cost_trend
ORDER BY period;

-- Chart Settings:
--   Stack: Yes
--   Value Format: R$ #,##0.00
--   Title: Monthly Cost Trend (BRL)

-- ============================================================================
-- Region 14: Infrastructure Summary (Static Content)
-- ============================================================================
-- Type: Static Content
-- Source > HTML:

/*
<div style="display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; padding: 10px;">

  <div style="background: linear-gradient(135deg, #0d419d 0%, #1f6feb 100%); border-radius: 16px; padding: 24px 32px; min-width: 180px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">Terraform</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">43</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Resources Managed</div>
  </div>

  <div style="background: linear-gradient(135deg, #0d419d 0%, #1f6feb 100%); border-radius: 16px; padding: 24px 32px; min-width: 180px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">Features</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">402</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Columns in Gold</div>
  </div>

  <div style="background: linear-gradient(135deg, #0d419d 0%, #1f6feb 100%); border-radius: 16px; padding: 24px 32px; min-width: 180px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">Selected</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">110</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Model Features</div>
  </div>

  <div style="background: linear-gradient(135deg, #1a7f37 0%, #2ea043 100%); border-radius: 16px; padding: 24px 32px; min-width: 180px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">Quality Gates</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">6/6</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">ALL PASS (QG-05)</div>
  </div>

  <div style="background: linear-gradient(135deg, #6e40c9 0%, #8957e5 100%); border-radius: 16px; padding: 24px 32px; min-width: 180px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">Cost Total</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">R$ 171</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">of R$ 500 Trial</div>
  </div>

  <div style="background: linear-gradient(135deg, #6e40c9 0%, #8957e5 100%); border-radius: 16px; padding: 24px 32px; min-width: 180px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="font-size: 14px; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">SAFRAs</div>
    <div style="font-size: 36px; font-weight: 700; color: #fff; margin: 8px 0;">6</div>
    <div style="font-size: 13px; color: rgba(255,255,255,0.7);">Oct 2024 - Mar 2025</div>
  </div>

</div>
*/

-- ============================================================================
-- STEP 5: App-level CSS (Shared Components > CSS)
-- ============================================================================
-- Go to: Shared Components > User Interface Attributes > CSS > Inline
-- Paste:

/*
:root {
  --chart-color-1: #1f6feb;
  --chart-color-2: #f97316;
  --chart-color-3: #2ea043;
  --chart-color-4: #da3633;
  --chart-color-5: #8957e5;
  --chart-color-6: #d29922;
}

.t-Region {
  border-radius: 12px !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
}

.t-Region-header {
  border-bottom: 2px solid var(--chart-color-1) !important;
}

.apex-chart .oj-chart-tooltip {
  border-radius: 8px !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}

.dashboard-badge-ok {
  background: #2ea043; color: white; padding: 4px 12px;
  border-radius: 20px; font-weight: 600; font-size: 12px;
}
.dashboard-badge-warning {
  background: #d29922; color: white; padding: 4px 12px;
  border-radius: 20px; font-weight: 600; font-size: 12px;
}
.dashboard-badge-danger {
  background: #da3633; color: white; padding: 4px 12px;
  border-radius: 20px; font-weight: 600; font-size: 12px;
}
*/

-- ============================================================================
-- DONE! Run the application:
-- https://G95D3985BD0D2FD-PODACADEMY2.adb.sa-saopaulo-1.oraclecloudapps.com/ords/r/mlmonitor/creditrisk/
-- ============================================================================
