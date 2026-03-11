-- NOTE: For production, prefer External Tables (see ../adw/02_create_external_tables.sql)
-- which read directly from Object Storage Parquet without data duplication.
-- The tables below are for the APEX monitoring dashboard only.
-- Gold data (clientes_consolidado, scores) should be queried via EXT_GOLD_* tables.

/*
 * Credit Risk ML Dashboard — Tables & Data
 * Run as MLMONITOR user in APEX SQL Workshop
 *
 * Tables:
 *   1. MODEL_PERFORMANCE    — KS, AUC, Gini per model per SAFRA
 *   2. SCORE_STABILITY      — PSI trend per model per SAFRA
 *   3. SCORE_DISTRIBUTION   — Score distribution stats per SAFRA
 *   4. FEATURE_DRIFT        — Per-feature PSI per SAFRA
 *   5. MODEL_STATUS         — Overall retrain status
 *   6. PIPELINE_RUNS        — Pipeline execution history
 *   7. COST_TRACKING        — Monthly cost breakdown
 */

---------------------------------------------------------------------------
-- 1. MODEL_PERFORMANCE
---------------------------------------------------------------------------
CREATE TABLE model_performance (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name      VARCHAR2(50)  NOT NULL,
    safra           VARCHAR2(6)   NOT NULL,
    dataset_type    VARCHAR2(10)  NOT NULL, -- TRAIN, OOS, OOT
    ks_statistic    NUMBER(10,5),
    auc_roc         NUMBER(10,5),
    gini            NUMBER(10,2),
    n_records       NUMBER,
    fpd_rate        NUMBER(10,4),
    evaluated_at    TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_perf UNIQUE (model_name, safra, dataset_type)
);

---------------------------------------------------------------------------
-- 2. SCORE_STABILITY
---------------------------------------------------------------------------
CREATE TABLE score_stability (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name      VARCHAR2(50)  NOT NULL,
    safra           VARCHAR2(6)   NOT NULL,
    score_psi       NUMBER(10,6),
    psi_status      VARCHAR2(20), -- OK, WARNING, RETRAIN
    train_mean      NUMBER(10,4),
    scoring_mean    NUMBER(10,4),
    train_n         NUMBER,
    scoring_n       NUMBER,
    measured_at     TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_stab UNIQUE (model_name, safra)
);

---------------------------------------------------------------------------
-- 3. SCORE_DISTRIBUTION
---------------------------------------------------------------------------
CREATE TABLE score_distribution (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name      VARCHAR2(50)  NOT NULL,
    safra           VARCHAR2(6)   NOT NULL,
    score_mean      NUMBER(10,2),
    score_median    NUMBER(10,2),
    score_p25       NUMBER(10,2),
    score_p75       NUMBER(10,2),
    score_std       NUMBER(10,2),
    pct_critico     NUMBER(5,2),  -- 0-299
    pct_alto        NUMBER(5,2),  -- 300-499
    pct_medio       NUMBER(5,2),  -- 500-699
    pct_baixo       NUMBER(5,2),  -- 700-1000
    total_scored    NUMBER,
    scored_at       TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_dist UNIQUE (model_name, safra)
);

---------------------------------------------------------------------------
-- 4. FEATURE_DRIFT
---------------------------------------------------------------------------
CREATE TABLE feature_drift (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name      VARCHAR2(50)  NOT NULL,
    safra           VARCHAR2(6)   NOT NULL,
    feature_name    VARCHAR2(100) NOT NULL,
    feature_psi     NUMBER(10,6),
    drift_status    VARCHAR2(20), -- OK, WARNING, RETRAIN
    train_mean      NUMBER(15,4),
    oot_mean        NUMBER(15,4),
    train_std       NUMBER(15,4),
    oot_std         NUMBER(15,4),
    measured_at     TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_drift UNIQUE (model_name, safra, feature_name)
);

---------------------------------------------------------------------------
-- 5. MODEL_STATUS
---------------------------------------------------------------------------
CREATE TABLE model_status (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name      VARCHAR2(50)  NOT NULL,
    model_version   VARCHAR2(50),
    status          VARCHAR2(20)  NOT NULL, -- STABLE, WARNING, RETRAIN_REQUIRED
    status_code     NUMBER(1)     NOT NULL, -- 0, 1, 2
    quality_gate    VARCHAR2(10), -- PASSED, FAILED
    last_trained    TIMESTAMP,
    last_scored     TIMESTAMP,
    last_monitored  TIMESTAMP,
    notes           VARCHAR2(500),
    updated_at      TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_status UNIQUE (model_name)
);

---------------------------------------------------------------------------
-- 6. PIPELINE_RUNS
---------------------------------------------------------------------------
CREATE TABLE pipeline_runs (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stage           VARCHAR2(20)  NOT NULL, -- BRONZE, SILVER, GOLD, TRAINING, SCORING, MONITORING
    status          VARCHAR2(20)  NOT NULL, -- SUCCESS, FAILED, RUNNING
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    duration_sec    NUMBER,
    records_in      NUMBER,
    records_out     NUMBER,
    notes           VARCHAR2(500)
);

---------------------------------------------------------------------------
-- 7. COST_TRACKING
---------------------------------------------------------------------------
CREATE TABLE cost_tracking (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    period          VARCHAR2(7)   NOT NULL, -- YYYY-MM
    service_name    VARCHAR2(50)  NOT NULL,
    cost_brl        NUMBER(10,2),
    pct_of_total    NUMBER(5,2),
    notes           VARCHAR2(200),
    CONSTRAINT uq_cost UNIQUE (period, service_name)
);

---------------------------------------------------------------------------
-- VIEWS for Dashboard
---------------------------------------------------------------------------

-- Performance comparison: Ensemble vs CatBoost side by side
CREATE OR REPLACE VIEW v_model_comparison AS
SELECT
    p1.safra,
    p1.dataset_type,
    p1.ks_statistic AS ensemble_ks,
    p1.auc_roc      AS ensemble_auc,
    p1.gini         AS ensemble_gini,
    p2.ks_statistic AS catboost_ks,
    p2.auc_roc      AS catboost_auc,
    p2.gini         AS catboost_gini
FROM model_performance p1
JOIN model_performance p2
  ON p1.safra = p2.safra AND p1.dataset_type = p2.dataset_type
WHERE p1.model_name = 'Ensemble_Average' AND p2.model_name = 'CatBoost';

-- Feature drift summary (per model)
CREATE OR REPLACE VIEW v_drift_summary AS
SELECT
    model_name,
    safra,
    COUNT(*) AS total_features,
    SUM(CASE WHEN drift_status = 'GREEN' THEN 1 ELSE 0 END) AS features_ok,
    SUM(CASE WHEN drift_status = 'YELLOW' THEN 1 ELSE 0 END) AS features_warning,
    SUM(CASE WHEN drift_status = 'RED' THEN 1 ELSE 0 END) AS features_retrain,
    ROUND(AVG(feature_psi), 6) AS avg_psi,
    MAX(feature_psi) AS max_psi
FROM feature_drift
GROUP BY model_name, safra;

-- Risk band evolution (per model)
CREATE OR REPLACE VIEW v_risk_evolution AS
SELECT
    model_name,
    safra,
    pct_critico,
    pct_alto,
    pct_medio,
    pct_baixo,
    total_scored,
    ROUND(pct_critico + pct_alto, 1) AS pct_high_risk
FROM score_distribution
ORDER BY model_name, safra;

-- Cost trend
CREATE OR REPLACE VIEW v_cost_trend AS
SELECT
    period,
    SUM(cost_brl) AS total_cost,
    MAX(CASE WHEN service_name LIKE '%Orchestrator%' THEN cost_brl END) AS orchestrator_cost,
    MAX(CASE WHEN service_name LIKE '%Data Flow%' THEN cost_brl END) AS dataflow_cost,
    MAX(CASE WHEN service_name LIKE '%Object Storage%' THEN cost_brl END) AS storage_cost
FROM cost_tracking
GROUP BY period
ORDER BY period;
