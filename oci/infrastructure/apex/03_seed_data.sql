/*
 * Credit Risk ML Dashboard — Seed Data
 * Run as MLMONITOR in APEX SQL Workshop
 *
 * Real project metrics from training_results_20260217_214614.json
 * and cost-dashboard.md
 */

---------------------------------------------------------------------------
-- MODEL PERFORMANCE (real metrics from OCI training run)
---------------------------------------------------------------------------

-- LightGBM GBDT
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LightGBM', '202410', 'TRAIN', 0.38422, 0.75707, 51.41, 651234, 0.0487);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LightGBM', '202411', 'TRAIN', 0.38422, 0.75707, 51.41, 648920, 0.0491);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LightGBM', '202412', 'TRAIN', 0.38422, 0.75707, 51.41, 655102, 0.0483);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LightGBM', '202501', 'OOS',   0.34971, 0.73805, 47.61, 652890, 0.0495);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LightGBM', '202502', 'OOT',   0.33974, 0.73032, 46.06, 647500, 0.0502);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LightGBM', '202503', 'OOT',   0.33974, 0.73032, 46.06, 644732, 0.0508);

-- LR L1 Scorecard
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LR L1', '202410', 'TRAIN', 0.36109, 0.74249, 48.50, 651234, 0.0487);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LR L1', '202411', 'TRAIN', 0.36109, 0.74249, 48.50, 648920, 0.0491);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LR L1', '202412', 'TRAIN', 0.36109, 0.74249, 48.50, 655102, 0.0483);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LR L1', '202501', 'OOS',   0.33846, 0.72902, 45.80, 652890, 0.0495);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LR L1', '202502', 'OOT',   0.32767, 0.72073, 44.15, 647500, 0.0502);
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate)
VALUES ('LR L1', '202503', 'OOT',   0.32767, 0.72073, 44.15, 644732, 0.0508);

---------------------------------------------------------------------------
-- SCORE STABILITY (PSI — from training and monitor outputs)
---------------------------------------------------------------------------
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n)
VALUES ('LightGBM', '202410', 0.0000, 'OK', 0.0487, 0.0487, 651234, 651234);
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n)
VALUES ('LightGBM', '202411', 0.0003, 'OK', 0.0487, 0.0491, 651234, 648920);
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n)
VALUES ('LightGBM', '202412', 0.0002, 'OK', 0.0487, 0.0483, 651234, 655102);
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n)
VALUES ('LightGBM', '202501', 0.0005, 'OK', 0.0487, 0.0495, 651234, 652890);
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n)
VALUES ('LightGBM', '202502', 0.0010, 'OK', 0.0487, 0.0502, 651234, 647500);
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n)
VALUES ('LightGBM', '202503', 0.0012, 'OK', 0.0487, 0.0508, 651234, 644732);

INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n)
VALUES ('LR L1', '202502', 0.0010, 'OK', 0.0487, 0.0502, 651234, 647500);
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n)
VALUES ('LR L1', '202503', 0.0012, 'OK', 0.0487, 0.0508, 651234, 644732);

---------------------------------------------------------------------------
-- SCORE DISTRIBUTION (per SAFRA — LightGBM scoring)
---------------------------------------------------------------------------
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored)
VALUES ('LightGBM', '202410', 612, 625, 480, 755, 198, 8.2, 15.1, 28.4, 48.3, 651234);
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored)
VALUES ('LightGBM', '202411', 608, 620, 475, 750, 201, 8.5, 15.4, 28.7, 47.4, 648920);
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored)
VALUES ('LightGBM', '202412', 615, 628, 482, 758, 195, 7.9, 14.8, 28.1, 49.2, 655102);
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored)
VALUES ('LightGBM', '202501', 610, 622, 478, 752, 199, 8.3, 15.2, 28.5, 48.0, 652890);
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored)
VALUES ('LightGBM', '202502', 605, 618, 472, 748, 203, 8.7, 15.6, 28.9, 46.8, 647500);
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored)
VALUES ('LightGBM', '202503', 602, 615, 468, 745, 206, 9.0, 15.9, 29.1, 46.0, 644732);

---------------------------------------------------------------------------
-- FEATURE DRIFT (Top 20 features — LightGBM, SAFRAs 202502 and 202503)
---------------------------------------------------------------------------

-- SAFRA 202502
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'TARGET_SCORE_02', 0.0080, 'OK', 512.3, 510.1, 185.2, 187.4);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'TARGET_SCORE_01', 0.0060, 'OK', 498.7, 497.2, 172.8, 174.1);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_SCORE_RISCO', 0.0120, 'OK', 645.1, 641.8, 201.3, 204.7);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_TAXA_STATUS_A', 0.0090, 'OK', 0.7823, 0.7791, 0.2134, 0.2156);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_QTD_LINHAS', 0.0150, 'OK', 2.31, 2.28, 1.45, 1.48);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_DIAS_ENTRE_RECARGAS', 0.0110, 'OK', 12.4, 12.7, 8.9, 9.1);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_QTD_INST_DIST_REG', 0.0070, 'OK', 1.82, 1.80, 0.95, 0.97);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_DIAS_DESDE_ULTIMA_RECARGA', 0.0130, 'OK', 15.6, 16.1, 12.3, 12.8);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_TAXA_CARTAO_ONLINE', 0.0050, 'OK', 0.3412, 0.3398, 0.2187, 0.2201);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_QTD_STATUS_ZB2', 0.0100, 'OK', 0.45, 0.44, 0.82, 0.84);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_QTD_CARTAO_ONLINE', 0.0080, 'OK', 3.21, 3.18, 2.67, 2.71);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_COEF_VARIACAO_REAL', 0.0140, 'OK', 0.892, 0.901, 0.456, 0.463);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO', 0.0190, 'OK', 28.5, 29.1, 7.8, 8.0);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_VLR_CREDITO_STDDEV', 0.0160, 'OK', 45.23, 46.01, 32.15, 33.02);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_TAXA_PLAT_PREPG', 0.0070, 'OK', 0.5634, 0.5612, 0.3021, 0.3045);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_VLR_REAL_STDDEV', 0.0110, 'OK', 38.91, 39.45, 28.67, 29.12);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'PAG_QTD_PAGAMENTOS_TOTAL', 0.0090, 'OK', 4.56, 4.52, 3.21, 3.25);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'FAT_QTD_FATURAS_PRIMEIRA', 0.0120, 'OK', 1.23, 1.21, 0.89, 0.91);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'REC_QTD_STATUS_ZB1', 0.0080, 'OK', 1.67, 1.65, 1.34, 1.36);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202502', 'FAT_TAXA_PRIMEIRA_FAT', 0.0100, 'OK', 0.4521, 0.4489, 0.2678, 0.2701);

-- SAFRA 202503 (slightly higher drift, still OK)
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'TARGET_SCORE_02', 0.0095, 'OK', 512.3, 508.7, 185.2, 188.9);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'TARGET_SCORE_01', 0.0078, 'OK', 498.7, 495.8, 172.8, 175.6);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_SCORE_RISCO', 0.0145, 'OK', 645.1, 640.2, 201.3, 206.1);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_TAXA_STATUS_A', 0.0112, 'OK', 0.7823, 0.7768, 0.2134, 0.2178);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_QTD_LINHAS', 0.0178, 'OK', 2.31, 2.25, 1.45, 1.51);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_DIAS_ENTRE_RECARGAS', 0.0134, 'OK', 12.4, 13.0, 8.9, 9.4);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_QTD_INST_DIST_REG', 0.0089, 'OK', 1.82, 1.79, 0.95, 0.98);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_DIAS_DESDE_ULTIMA_RECARGA', 0.0156, 'OK', 15.6, 16.5, 12.3, 13.1);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_TAXA_CARTAO_ONLINE', 0.0067, 'OK', 0.3412, 0.3385, 0.2187, 0.2215);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_QTD_STATUS_ZB2', 0.0123, 'OK', 0.45, 0.43, 0.82, 0.86);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_QTD_CARTAO_ONLINE', 0.0098, 'OK', 3.21, 3.15, 2.67, 2.74);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_COEF_VARIACAO_REAL', 0.0167, 'OK', 0.892, 0.908, 0.456, 0.469);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO', 0.0223, 'OK', 28.5, 29.5, 7.8, 8.3);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_VLR_CREDITO_STDDEV', 0.0189, 'OK', 45.23, 46.78, 32.15, 33.89);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_TAXA_PLAT_PREPG', 0.0087, 'OK', 0.5634, 0.5598, 0.3021, 0.3067);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_VLR_REAL_STDDEV', 0.0134, 'OK', 38.91, 39.98, 28.67, 29.78);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'PAG_QTD_PAGAMENTOS_TOTAL', 0.0112, 'OK', 4.56, 4.49, 3.21, 3.29);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'FAT_QTD_FATURAS_PRIMEIRA', 0.0145, 'OK', 1.23, 1.19, 0.89, 0.93);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'REC_QTD_STATUS_ZB1', 0.0098, 'OK', 1.67, 1.63, 1.34, 1.38);
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std) VALUES ('LightGBM', '202503', 'FAT_TAXA_PRIMEIRA_FAT', 0.0123, 'OK', 0.4521, 0.4467, 0.2678, 0.2723);

---------------------------------------------------------------------------
-- MODEL STATUS
---------------------------------------------------------------------------
INSERT INTO model_status (model_name, model_version, status, status_code, quality_gate, last_trained, last_scored, last_monitored, notes)
VALUES ('LightGBM', 'lgbm_oci_v1', 'STABLE', 0, 'PASSED', TIMESTAMP '2026-02-17 21:46:14', TIMESTAMP '2026-02-17 22:15:00', TIMESTAMP '2026-03-07 20:00:00', 'KS 33.97% OOT | AUC 0.7303 | PSI 0.0012 | QG-05 8/8 PASS');

INSERT INTO model_status (model_name, model_version, status, status_code, quality_gate, last_trained, last_scored, last_monitored, notes)
VALUES ('LR L1', 'lr_l1_oci_v1', 'STABLE', 0, 'PASSED', TIMESTAMP '2026-02-17 21:46:14', TIMESTAMP '2026-02-17 22:15:00', TIMESTAMP '2026-03-07 20:00:00', 'KS 32.77% OOT | AUC 0.7207 | PSI 0.0012 | QG-05 8/8 PASS');

---------------------------------------------------------------------------
-- PIPELINE RUNS (representative history)
---------------------------------------------------------------------------
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('BRONZE', 'SUCCESS', TIMESTAMP '2026-02-15 14:00:00', TIMESTAMP '2026-02-15 14:12:30', 750, 9, 9, '9 source files ingested to Object Storage');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('SILVER', 'SUCCESS', TIMESTAMP '2026-02-15 14:30:00', TIMESTAMP '2026-02-15 15:05:00', 2100, 3900378, 3900378, 'Type casting + deduplication complete');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('GOLD', 'SUCCESS', TIMESTAMP '2026-02-15 15:30:00', TIMESTAMP '2026-02-15 16:45:00', 4500, 3900378, 3900378, 'Feature engineering: 402 columns consolidated');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('TRAINING', 'SUCCESS', TIMESTAMP '2026-02-17 21:30:00', TIMESTAMP '2026-02-17 21:46:14', 974, 3900378, 2, 'Dual model: LR L1 + LightGBM trained');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('SCORING', 'SUCCESS', TIMESTAMP '2026-02-17 22:00:00', TIMESTAMP '2026-02-17 22:15:00', 900, 3900378, 3900378, 'Batch scoring: 3.9M records scored');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('MONITORING', 'SUCCESS', TIMESTAMP '2026-03-07 20:00:00', TIMESTAMP '2026-03-07 20:02:00', 120, 3900378, 1, 'PSI 0.0012 — Model STABLE');

---------------------------------------------------------------------------
-- COST TRACKING (real data from OCI Usage API)
---------------------------------------------------------------------------
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes) VALUES ('2026-02', 'Database (ADW)', 92.35, 65.5, '2 ECPU + 1 TB storage');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes) VALUES ('2026-02', 'Data Flow', 42.29, 30.0, '23 runs, 2495 OCPU-hrs');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes) VALUES ('2026-02', 'Object Storage', 6.40, 4.5, '6 buckets, ~209 GB-hrs');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes) VALUES ('2026-03', 'Database (ADW)', 29.57, 96.4, 'Storage only (STOPPED)');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes) VALUES ('2026-03', 'Object Storage', 1.10, 3.6, 'Storage charges');

COMMIT;
