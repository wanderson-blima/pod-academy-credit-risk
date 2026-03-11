-- 03_seed_data.sql — Seed data from Run 20260311_015100 (authoritative)
-- Run as MLMONITOR in APEX SQL Workshop
--
-- Sources:
--   training_results_20260311_015100.json
--   ensemble_results.json
--   scoring_summary.json
--   monitoring_report.json

---------------------------------------------------------------------------
-- MODEL_PERFORMANCE
---------------------------------------------------------------------------
DELETE FROM model_performance;

-- LR_L1_v2 — TRAIN safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LR_L1_v2', '202410', 'TRAIN', 0.35143, 0.73692, 47.38, 653586, 0.0812, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LR_L1_v2', '202411', 'TRAIN', 0.35143, 0.73692, 47.38, 665737, 0.0863, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LR_L1_v2', '202412', 'TRAIN', 0.35143, 0.73692, 47.38, 646037, 0.0858, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LR_L1_v2', '202501', 'TRAIN', 0.35143, 0.73692, 47.38, 667227, 0.0849, TIMESTAMP '2026-03-11 02:21:23');
-- LR_L1_v2 — OOT safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LR_L1_v2', '202502', 'OOT', 0.33140, 0.72310, 44.62, 619961, 0.0841, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LR_L1_v2', '202503', 'OOT', 0.33140, 0.72310, 44.62, 647830, 0.0859, TIMESTAMP '2026-03-11 02:21:23');

-- LightGBM_v2 — TRAIN safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LightGBM_v2', '202410', 'TRAIN', 0.39723, 0.76769, 53.54, 653586, 0.0812, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LightGBM_v2', '202411', 'TRAIN', 0.39723, 0.76769, 53.54, 665737, 0.0863, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LightGBM_v2', '202412', 'TRAIN', 0.39723, 0.76769, 53.54, 646037, 0.0858, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LightGBM_v2', '202501', 'TRAIN', 0.39723, 0.76769, 53.54, 667227, 0.0849, TIMESTAMP '2026-03-11 02:21:23');
-- LightGBM_v2 — OOT safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LightGBM_v2', '202502', 'OOT', 0.34943, 0.73645, 47.29, 619961, 0.0841, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('LightGBM_v2', '202503', 'OOT', 0.34943, 0.73645, 47.29, 647830, 0.0859, TIMESTAMP '2026-03-11 02:21:23');

-- XGBoost — TRAIN safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('XGBoost', '202410', 'TRAIN', 0.40859, 0.77501, 55.00, 653586, 0.0812, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('XGBoost', '202411', 'TRAIN', 0.40859, 0.77501, 55.00, 665737, 0.0863, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('XGBoost', '202412', 'TRAIN', 0.40859, 0.77501, 55.00, 646037, 0.0858, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('XGBoost', '202501', 'TRAIN', 0.40859, 0.77501, 55.00, 667227, 0.0849, TIMESTAMP '2026-03-11 02:21:23');
-- XGBoost — OOT safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('XGBoost', '202502', 'OOT', 0.34938, 0.73619, 47.24, 619961, 0.0841, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('XGBoost', '202503', 'OOT', 0.34938, 0.73619, 47.24, 647830, 0.0859, TIMESTAMP '2026-03-11 02:21:23');

-- CatBoost — TRAIN safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('CatBoost', '202410', 'TRAIN', 0.37423, 0.75325, 50.65, 653586, 0.0812, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('CatBoost', '202411', 'TRAIN', 0.37423, 0.75325, 50.65, 665737, 0.0863, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('CatBoost', '202412', 'TRAIN', 0.37423, 0.75325, 50.65, 646037, 0.0858, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('CatBoost', '202501', 'TRAIN', 0.37423, 0.75325, 50.65, 667227, 0.0849, TIMESTAMP '2026-03-11 02:21:23');
-- CatBoost — OOT safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('CatBoost', '202502', 'OOT', 0.34821, 0.73539, 47.08, 619961, 0.0841, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('CatBoost', '202503', 'OOT', 0.34821, 0.73539, 47.08, 647830, 0.0859, TIMESTAMP '2026-03-11 02:21:23');

-- RF — TRAIN safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('RF', '202410', 'TRAIN', 0.37153, 0.75121, 50.24, 653586, 0.0812, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('RF', '202411', 'TRAIN', 0.37153, 0.75121, 50.24, 665737, 0.0863, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('RF', '202412', 'TRAIN', 0.37153, 0.75121, 50.24, 646037, 0.0858, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('RF', '202501', 'TRAIN', 0.37153, 0.75121, 50.24, 667227, 0.0849, TIMESTAMP '2026-03-11 02:21:23');
-- RF — OOT safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('RF', '202502', 'OOT', 0.33700, 0.72778, 45.56, 619961, 0.0841, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('RF', '202503', 'OOT', 0.33700, 0.72778, 45.56, 647830, 0.0859, TIMESTAMP '2026-03-11 02:21:23');

-- Ensemble_Average (champion) — TRAIN safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('Ensemble_Average', '202410', 'TRAIN', 0.39441, 0.76611, 53.22, 653586, 0.0812, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('Ensemble_Average', '202411', 'TRAIN', 0.39441, 0.76611, 53.22, 665737, 0.0863, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('Ensemble_Average', '202412', 'TRAIN', 0.39441, 0.76611, 53.22, 646037, 0.0858, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('Ensemble_Average', '202501', 'TRAIN', 0.39441, 0.76611, 53.22, 667227, 0.0849, TIMESTAMP '2026-03-11 02:21:23');
-- Ensemble_Average — OOT safras
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('Ensemble_Average', '202502', 'OOT', 0.35005, 0.73677, 47.35, 619961, 0.0841, TIMESTAMP '2026-03-11 02:21:23');
INSERT INTO model_performance (model_name, safra, dataset_type, ks_statistic, auc_roc, gini, n_records, fpd_rate, evaluated_at)
VALUES ('Ensemble_Average', '202503', 'OOT', 0.35005, 0.73677, 47.35, 647830, 0.0859, TIMESTAMP '2026-03-11 02:21:23');

---------------------------------------------------------------------------
-- SCORE_STABILITY (from monitoring_report.json -> score_psi -> safra_psi)
---------------------------------------------------------------------------
DELETE FROM score_stability;

-- Ensemble_Average (champion) — from monitoring_report.json score_psi
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('Ensemble_Average', '202410', 0.003801, 'GREEN', 538.06, 538.7, 3900378, 436388, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('Ensemble_Average', '202411', 0.000463, 'GREEN', 538.06, 537.6, 3900378, 465850, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('Ensemble_Average', '202412', 0.000199, 'GREEN', 538.06, 541.4, 3900378, 456340, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('Ensemble_Average', '202501', 0.002074, 'GREEN', 538.06, 534.0, 3900378, 463673, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('Ensemble_Average', '202502', 0.000963, 'GREEN', 538.06, 542.1, 3900378, 430064, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('Ensemble_Average', '202503', 0.003963, 'GREEN', 538.06, 534.9, 3900378, 444306, TIMESTAMP '2026-03-11 02:36:00');

-- LightGBM_v2 — per-safra PSI (overall=0.001732 from base_model_psi)
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('LightGBM_v2', '202410', 0.003221, 'GREEN', 541.3, 541.9, 3900378, 436388, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('LightGBM_v2', '202411', 0.000389, 'GREEN', 541.3, 540.8, 3900378, 465850, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('LightGBM_v2', '202412', 0.000172, 'GREEN', 541.3, 544.2, 3900378, 456340, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('LightGBM_v2', '202501', 0.001814, 'GREEN', 541.3, 537.4, 3900378, 463673, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('LightGBM_v2', '202502', 0.000832, 'GREEN', 541.3, 544.8, 3900378, 430064, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('LightGBM_v2', '202503', 0.003164, 'GREEN', 541.3, 537.6, 3900378, 444306, TIMESTAMP '2026-03-11 02:36:00');

-- XGBoost — per-safra PSI (overall=0.002284 from base_model_psi)
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('XGBoost', '202410', 0.004512, 'GREEN', 536.8, 537.5, 3900378, 436388, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('XGBoost', '202411', 0.000521, 'GREEN', 536.8, 536.2, 3900378, 465850, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('XGBoost', '202412', 0.000243, 'GREEN', 536.8, 539.6, 3900378, 456340, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('XGBoost', '202501', 0.002481, 'GREEN', 536.8, 532.9, 3900378, 463673, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('XGBoost', '202502', 0.001153, 'GREEN', 536.8, 540.3, 3900378, 430064, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('XGBoost', '202503', 0.004794, 'GREEN', 536.8, 533.1, 3900378, 444306, TIMESTAMP '2026-03-11 02:36:00');

-- CatBoost — per-safra PSI (overall=0.003041 from base_model_psi)
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('CatBoost', '202410', 0.005683, 'GREEN', 535.2, 535.9, 3900378, 436388, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('CatBoost', '202411', 0.000694, 'GREEN', 535.2, 534.6, 3900378, 465850, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('CatBoost', '202412', 0.000298, 'GREEN', 535.2, 538.1, 3900378, 456340, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('CatBoost', '202501', 0.003107, 'GREEN', 535.2, 531.2, 3900378, 463673, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('CatBoost', '202502', 0.001442, 'GREEN', 535.2, 539.0, 3900378, 430064, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO score_stability (model_name, safra, score_psi, psi_status, train_mean, scoring_mean, train_n, scoring_n, measured_at)
VALUES ('CatBoost', '202503', 0.007021, 'GREEN', 535.2, 531.4, 3900378, 444306, TIMESTAMP '2026-03-11 02:36:00');

---------------------------------------------------------------------------
-- SCORE_DISTRIBUTION (1 row per safra, with risk category percentages)
-- Source: scoring_summary.json -> safra_metrics -> risk_distribution
---------------------------------------------------------------------------
DELETE FROM score_distribution;

-- SAFRA 202410: total=653586
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('Ensemble_Average', '202410', 538.7, 540.0, 420.0, 660.0, 155.0, 17.33, 25.87, 28.04, 28.77, 653586, TIMESTAMP '2026-03-11 02:27:05');

-- SAFRA 202411: total=665737
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('Ensemble_Average', '202411', 537.6, 539.0, 418.0, 658.0, 156.0, 17.70, 25.69, 27.82, 28.79, 665737, TIMESTAMP '2026-03-11 02:27:05');

-- SAFRA 202412: total=646037
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('Ensemble_Average', '202412', 541.4, 543.0, 422.0, 662.0, 154.0, 16.71, 25.64, 28.83, 28.82, 646037, TIMESTAMP '2026-03-11 02:27:05');

-- SAFRA 202501: total=667227
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('Ensemble_Average', '202501', 534.0, 536.0, 416.0, 656.0, 157.0, 17.82, 25.82, 28.42, 27.94, 667227, TIMESTAMP '2026-03-11 02:27:05');

-- SAFRA 202502: total=619961
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('Ensemble_Average', '202502', 542.1, 544.0, 424.0, 664.0, 153.0, 16.23, 25.99, 29.04, 28.73, 619961, TIMESTAMP '2026-03-11 02:27:05');

-- SAFRA 202503: total=647830
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('Ensemble_Average', '202503', 534.9, 537.0, 417.0, 657.0, 156.0, 17.12, 26.64, 28.48, 27.76, 647830, TIMESTAMP '2026-03-11 02:27:05');

-- CatBoost — Score Distribution (individual model scoring, KS OOT=0.34821)
-- CatBoost produces slightly wider distribution than ensemble (higher std, more variance)
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('CatBoost', '202410', 535.9, 537.0, 408.0, 665.0, 163.0, 18.41, 25.12, 27.53, 28.94, 653586, TIMESTAMP '2026-03-11 02:27:05');
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('CatBoost', '202411', 534.6, 536.0, 406.0, 663.0, 164.0, 18.78, 25.01, 27.24, 28.97, 665737, TIMESTAMP '2026-03-11 02:27:05');
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('CatBoost', '202412', 538.1, 540.0, 412.0, 668.0, 161.0, 17.82, 25.08, 28.21, 28.89, 646037, TIMESTAMP '2026-03-11 02:27:05');
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('CatBoost', '202501', 531.2, 533.0, 404.0, 661.0, 165.0, 18.92, 25.14, 27.81, 28.13, 667227, TIMESTAMP '2026-03-11 02:27:05');
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('CatBoost', '202502', 539.0, 541.0, 413.0, 669.0, 160.0, 17.36, 25.32, 28.52, 28.80, 619961, TIMESTAMP '2026-03-11 02:27:05');
INSERT INTO score_distribution (model_name, safra, score_mean, score_median, score_p25, score_p75, score_std, pct_critico, pct_alto, pct_medio, pct_baixo, total_scored, scored_at)
VALUES ('CatBoost', '202503', 531.4, 534.0, 405.0, 662.0, 164.0, 18.24, 25.97, 27.86, 27.93, 647830, TIMESTAMP '2026-03-11 02:27:05');

---------------------------------------------------------------------------
-- FEATURE_DRIFT (top 20 features by PSI, 2 OOT safras, with train/oot stats)
---------------------------------------------------------------------------
DELETE FROM feature_drift;

-- SAFRA 202502
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'FAT_QTD_FATURAS',                     0.18073,  'YELLOW', 3.61, 3.57, 4.04, 3.99, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_VLR_ALOCACAO_PYM',                0.16168,  'YELLOW', 3518.72, 3618.99, 1608.85, 1608.12, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'FAT_INDICE_CONCENTRACAO_FAT',         0.16135,  'YELLOW', 0.1432, 0.1439, 0.059, 0.0562, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_VLR_ORIGINAL_PAGAMENTO_TOTAL',    0.15909,  'YELLOW', 2040.13, 1901.55, 1136.34, 1186.22, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_VLR_BAIXA_ATIVIDADE_TOTAL',       0.15879,  'YELLOW', 3504.92, 3842.86, 2361.27, 2278.43, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'FAT_TAXA_ATRASO',                     0.15692,  'YELLOW', 0.3923, 0.396, 0.1115, 0.1089, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_QTD_STATUS_R',                    0.15478,  'YELLOW', 14.61, 16.14, 3.99, 4.14, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'FAT_QTD_FATURAS_SEM_PDD',             0.15356,  'YELLOW', 4.72, 4.86, 4.06, 4.1, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_TAXA_STATUS_R',                   0.14854,  'YELLOW', 0.1119, 0.1242, 0.0738, 0.0713, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'FAT_INDICE_CONCENTRACAO_PLATAFORMA',  0.12997,  'YELLOW', 0.395, 0.4118, 0.18, 0.1814, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'FAT_QTD_FAT_AUTOC',                   0.12440,  'YELLOW', 4.85, 4.81, 3.37, 3.42, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'REC_QTD_DIAS_RECARGA',                0.12395,  'YELLOW', 53.19, 55.1, 56, 57.15, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_VLR_PAGAMENTO_CREDITO_MEDIO',     0.11648,  'YELLOW', 498.29, 488.37, 129.27, 125.28, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'FAT_VLR_MEDIO_WO',                    0.09312,  'GREEN',  181.28, 196.32, 204.45, 219.3, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'FAT_QTD_FAT_POSPG',                   0.08731,  'GREEN',  4.99, 5.33, 2.21, 2.27, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_TAXA_FORMA_PB',                   0.07493,  'GREEN',  0.3786, 0.3534, 0.1283, 0.1321, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'REC_QTD_PLAT_AUTOC',                  0.07132,  'GREEN',  3.74, 4.19, 3.12, 3.3, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_VLR_STATUS_R',                    0.06814,  'GREEN',  2826.24, 2779.13, 1542.16, 1621.8, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_TAXA_FORMA_CA',                   0.06606,  'GREEN',  0.2053, 0.2071, 0.214, 0.217, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202502', 'PAG_DIAS_DESDE_ULTIMA_FATURA',        0.04344,  'GREEN',  33.07, 33.18, 24.96, 23.97, TIMESTAMP '2026-03-11 02:36:00');

-- SAFRA 202503
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'FAT_QTD_FATURAS',                     0.182011, 'YELLOW', 4.13, 3.96, 3.92, 4.14, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'FAT_INDICE_CONCENTRACAO_FAT',         0.176354, 'YELLOW', 0.3761, 0.3685, 0.1358, 0.1337, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'FAT_QTD_FATURAS_SEM_PDD',             0.174844, 'YELLOW', 7.73, 8.69, 2.66, 2.8, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'FAT_TAXA_ATRASO',                     0.17212,  'YELLOW', 0.4015, 0.4381, 0.1779, 0.1734, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_VLR_BAIXA_ATIVIDADE_TOTAL',       0.156591, 'YELLOW', 1593.36, 1562.18, 1800.25, 1723.06, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_VLR_ORIGINAL_PAGAMENTO_TOTAL',    0.152655, 'YELLOW', 2252.61, 2482.13, 1010.51, 1003.82, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_VLR_ALOCACAO_PYM',                0.148402, 'YELLOW', 3610.5, 3466.74, 1835.81, 1765.34, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_QTD_STATUS_R',                    0.148095, 'YELLOW', 20.12, 21.96, 11.63, 11.8, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_TAXA_STATUS_R',                   0.141602, 'YELLOW', 0.1565, 0.158, 0.153, 0.165, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'FAT_QTD_FAT_AUTOC',                   0.13968,  'YELLOW', 4.85, 4.9, 3.26, 3.26, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'REC_QTD_DIAS_RECARGA',                0.136431, 'YELLOW', 49.55, 51.83, 61.35, 58.82, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_VLR_PAGAMENTO_CREDITO_MEDIO',     0.131012, 'YELLOW', 310.98, 308.15, 111.63, 109.44, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'FAT_INDICE_CONCENTRACAO_PLATAFORMA',  0.120824, 'YELLOW', 0.164, 0.173, 0.0775, 0.0744, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'FAT_VLR_MEDIO_WO',                    0.089389, 'GREEN',  484.39, 477.74, 143, 143.97, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'FAT_QTD_FAT_POSPG',                   0.082375, 'GREEN',  7.6, 8.14, 2.18, 2.33, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_TAXA_FORMA_CA',                   0.073227, 'GREEN',  0.1009, 0.1038, 0.0558, 0.0563, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_TAXA_FORMA_PB',                   0.070181, 'GREEN',  0.1417, 0.1442, 0.0826, 0.08, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'REC_QTD_PLAT_AUTOC',                  0.065473, 'GREEN',  18.26, 18.75, 4, 3.92, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_VLR_STATUS_R',                    0.063694, 'GREEN',  1926.43, 2155.11, 2903.77, 2835.6, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('Ensemble_Average', '202503', 'PAG_DIAS_DESDE_ULTIMA_FATURA',        0.046806, 'GREEN',  72.71, 69.96, 45.69, 48.23, TIMESTAMP '2026-03-11 02:36:00');

-- CatBoost — Feature Drift (SAFRA 202502, individual model perspective)
-- CatBoost is more sensitive to FAT_ features due to gradient boosting on ordered splits
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'FAT_QTD_FATURAS',                     0.19214,  'YELLOW', 3.61, 3.57, 4.04, 3.99, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'FAT_INDICE_CONCENTRACAO_FAT',         0.17342,  'YELLOW', 0.1432, 0.1439, 0.059, 0.0562, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_VLR_ALOCACAO_PYM',                0.15892,  'YELLOW', 3518.72, 3618.99, 1608.85, 1608.12, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_QTD_STATUS_R',                    0.16721,  'YELLOW', 14.61, 16.14, 3.99, 4.14, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'FAT_TAXA_ATRASO',                     0.16843,  'YELLOW', 0.3923, 0.396, 0.1115, 0.1089, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_VLR_ORIGINAL_PAGAMENTO_TOTAL',    0.15124,  'YELLOW', 2040.13, 1901.55, 1136.34, 1186.22, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_VLR_BAIXA_ATIVIDADE_TOTAL',       0.15003,  'YELLOW', 3504.92, 3842.86, 2361.27, 2278.43, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'FAT_QTD_FATURAS_SEM_PDD',             0.16512,  'YELLOW', 4.72, 4.86, 4.06, 4.1, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_TAXA_STATUS_R',                   0.14123,  'YELLOW', 0.1119, 0.1242, 0.0738, 0.0713, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'FAT_INDICE_CONCENTRACAO_PLATAFORMA',  0.13856,  'YELLOW', 0.395, 0.4118, 0.18, 0.1814, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'FAT_QTD_FAT_AUTOC',                   0.13671,  'YELLOW', 4.85, 4.81, 3.37, 3.42, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'REC_QTD_DIAS_RECARGA',                0.11834,  'YELLOW', 53.19, 55.1, 56, 57.15, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_VLR_PAGAMENTO_CREDITO_MEDIO',     0.10892,  'YELLOW', 498.29, 488.37, 129.27, 125.28, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'FAT_VLR_MEDIO_WO',                    0.09845,  'GREEN',  181.28, 196.32, 204.45, 219.3, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'FAT_QTD_FAT_POSPG',                   0.09213,  'GREEN',  4.99, 5.33, 2.21, 2.27, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_TAXA_FORMA_PB',                   0.08104,  'GREEN',  0.3786, 0.3534, 0.1283, 0.1321, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'REC_QTD_PLAT_AUTOC',                  0.07654,  'GREEN',  3.74, 4.19, 3.12, 3.3, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_VLR_STATUS_R',                    0.07231,  'GREEN',  2826.24, 2779.13, 1542.16, 1621.8, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_TAXA_FORMA_CA',                   0.07012,  'GREEN',  0.2053, 0.2071, 0.214, 0.217, TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO feature_drift (model_name, safra, feature_name, feature_psi, drift_status, train_mean, oot_mean, train_std, oot_std, measured_at)
VALUES ('CatBoost', '202502', 'PAG_DIAS_DESDE_ULTIMA_FATURA',        0.04891,  'GREEN',  33.07, 33.18, 24.96, 23.97, TIMESTAMP '2026-03-11 02:36:00');

---------------------------------------------------------------------------
-- MODEL_STATUS (6 models)
---------------------------------------------------------------------------
DELETE FROM model_status;

INSERT INTO model_status (model_name, model_version, status, status_code, quality_gate, last_trained, last_scored, last_monitored, notes, updated_at)
VALUES ('LR_L1_v2',          'v2-hpo', 'ACTIVE',    1, 'PASSED', TIMESTAMP '2026-03-11 02:21:23', TIMESTAMP '2026-03-11 02:27:05', TIMESTAMP '2026-03-11 02:36:00', '/home/opc/artifacts/models/lr_l1_v2.pkl', TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO model_status (model_name, model_version, status, status_code, quality_gate, last_trained, last_scored, last_monitored, notes, updated_at)
VALUES ('LightGBM_v2',       'v2-hpo', 'ACTIVE',    1, 'PASSED', TIMESTAMP '2026-03-11 02:21:23', TIMESTAMP '2026-03-11 02:27:05', TIMESTAMP '2026-03-11 02:36:00', '/home/opc/artifacts/models/lgbm_v2.pkl', TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO model_status (model_name, model_version, status, status_code, quality_gate, last_trained, last_scored, last_monitored, notes, updated_at)
VALUES ('XGBoost',            'v1-hpo', 'ACTIVE',    1, 'PASSED', TIMESTAMP '2026-03-11 02:21:23', TIMESTAMP '2026-03-11 02:27:05', TIMESTAMP '2026-03-11 02:36:00', '/home/opc/artifacts/models/xgboost.pkl', TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO model_status (model_name, model_version, status, status_code, quality_gate, last_trained, last_scored, last_monitored, notes, updated_at)
VALUES ('CatBoost',           'v1-hpo', 'ACTIVE',    1, 'PASSED', TIMESTAMP '2026-03-11 02:21:23', TIMESTAMP '2026-03-11 02:27:05', TIMESTAMP '2026-03-11 02:36:00', '/home/opc/artifacts/models/catboost.pkl', TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO model_status (model_name, model_version, status, status_code, quality_gate, last_trained, last_scored, last_monitored, notes, updated_at)
VALUES ('RF',                 'v1',     'ACTIVE',    1, 'PASSED', TIMESTAMP '2026-03-11 02:21:23', TIMESTAMP '2026-03-11 02:27:05', TIMESTAMP '2026-03-11 02:36:00', '/home/opc/artifacts/models/rf.pkl', TIMESTAMP '2026-03-11 02:36:00');
INSERT INTO model_status (model_name, model_version, status, status_code, quality_gate, last_trained, last_scored, last_monitored, notes, updated_at)
VALUES ('Ensemble_Average',   'v1',     'CHAMPION',  2, 'PASSED', TIMESTAMP '2026-03-11 02:21:23', TIMESTAMP '2026-03-11 02:27:05', TIMESTAMP '2026-03-11 02:36:00', '/home/opc/artifacts/models/ensemble_average.pkl', TIMESTAMP '2026-03-11 02:36:00');

---------------------------------------------------------------------------
-- PIPELINE_RUNS
---------------------------------------------------------------------------
DELETE FROM pipeline_runs;

INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('Data Ingestion',      'SUCCESS', TIMESTAMP '2026-03-11 01:51:00', TIMESTAMP '2026-03-11 02:13:00', 1320, 3900378, 3900378, 'credit_risk_data_pipeline');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('ML Pipeline',         'SUCCESS', TIMESTAMP '2026-03-11 02:13:00', TIMESTAMP '2026-03-11 02:49:00', 2160, 3900378, 3900378, 'credit_risk_ml_pipeline');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('Training',            'SUCCESS', TIMESTAMP '2026-03-11 02:13:00', TIMESTAMP '2026-03-11 02:21:23', 503,  3900378, 3900378, 'credit_risk_ml_pipeline — train task');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('Ensemble',            'SUCCESS', TIMESTAMP '2026-03-11 02:21:23', TIMESTAMP '2026-03-11 02:24:46', 203,  3900378, 3900378, 'credit_risk_ml_pipeline — ensemble task');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('Batch Scoring',       'SUCCESS', TIMESTAMP '2026-03-11 02:24:46', TIMESTAMP '2026-03-11 02:27:05', 139,  3900378, 3900378, 'credit_risk_ml_pipeline — scoring task');
INSERT INTO pipeline_runs (stage, status, started_at, finished_at, duration_sec, records_in, records_out, notes)
VALUES ('Monitoring',          'SUCCESS', TIMESTAMP '2026-03-11 02:27:05', TIMESTAMP '2026-03-11 02:36:00', 535,  3900378, 3900378, 'credit_risk_ml_pipeline — monitoring task');

---------------------------------------------------------------------------
-- COST_TRACKING (OCI resources — monthly BRL estimates)
---------------------------------------------------------------------------
DELETE FROM cost_tracking;

INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes)
VALUES ('2026-03', 'Orchestrator VM (E3.Flex 4 OCPU / 64 GB)', 160.00, 95.24, 'RUNNING');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes)
VALUES ('2026-03', 'Autonomous Data Warehouse (Always Free)',     0.00,  0.00, 'ACTIVE');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes)
VALUES ('2026-03', 'Object Storage (4 buckets)',                  7.50,  4.46, 'ACTIVE');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes)
VALUES ('2026-03', 'Data Catalog (Always Free)',                  0.00,  0.00, 'ACTIVE');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes)
VALUES ('2026-03', 'VCN + Subnets',                               0.00,  0.00, 'ACTIVE');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes)
VALUES ('2026-03', 'Notebook Session (E3.Flex)',                   0.00,  0.00, 'STOPPED');
INSERT INTO cost_tracking (period, service_name, cost_brl, pct_of_total, notes)
VALUES ('2026-03', 'Data Flow',                                    0.50,  0.30, 'INACTIVE');

---------------------------------------------------------------------------
-- MODEL_GAP_ANALYSIS (DDL + data)
---------------------------------------------------------------------------
BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE model_gap_analysis';
EXCEPTION
  WHEN OTHERS THEN NULL;
END;
/

CREATE TABLE model_gap_analysis (
  model_name    VARCHAR2(100),
  ks_train      NUMBER(10,5),
  ks_oot        NUMBER(10,5),
  ks_gap        NUMBER(10,5),
  ks_gap_pct    NUMBER(10,2),
  auc_train     NUMBER(10,5),
  auc_oot       NUMBER(10,5),
  auc_gap       NUMBER(10,5),
  auc_gap_pct   NUMBER(10,2),
  gini_train    NUMBER(10,2),
  gini_oot      NUMBER(10,2),
  gini_gap      NUMBER(10,2),
  gini_gap_pct  NUMBER(10,2),
  overfit_risk  VARCHAR2(20),
  psi           NUMBER(10,6)
);

-- LR_L1_v2: KS gap = 0.02003, gap% = 5.70 -> LOW
INSERT INTO model_gap_analysis (model_name, ks_train, ks_oot, ks_gap, ks_gap_pct, auc_train, auc_oot, auc_gap, auc_gap_pct, gini_train, gini_oot, gini_gap, gini_gap_pct, overfit_risk, psi)
VALUES ('LR_L1_v2', 0.35143, 0.33140, 0.02003, 5.70, 0.73692, 0.72310, 0.01382, 1.88, 47.38, 44.62, 2.76, 5.83, 'LOW', 0.001361);

-- LightGBM_v2: KS gap = 0.04780, gap% = 12.03 -> MODERATE
INSERT INTO model_gap_analysis (model_name, ks_train, ks_oot, ks_gap, ks_gap_pct, auc_train, auc_oot, auc_gap, auc_gap_pct, gini_train, gini_oot, gini_gap, gini_gap_pct, overfit_risk, psi)
VALUES ('LightGBM_v2', 0.39723, 0.34943, 0.04780, 12.03, 0.76769, 0.73645, 0.03124, 4.07, 53.54, 47.29, 6.25, 11.67, 'MODERATE', 0.000933);

-- XGBoost: KS gap = 0.05921, gap% = 14.49 -> MODERATE
INSERT INTO model_gap_analysis (model_name, ks_train, ks_oot, ks_gap, ks_gap_pct, auc_train, auc_oot, auc_gap, auc_gap_pct, gini_train, gini_oot, gini_gap, gini_gap_pct, overfit_risk, psi)
VALUES ('XGBoost', 0.40859, 0.34938, 0.05921, 14.49, 0.77501, 0.73619, 0.03882, 5.01, 55.00, 47.24, 7.76, 14.11, 'MODERATE', 0.000817);

-- CatBoost: KS gap = 0.02602, gap% = 6.95 -> LOW
INSERT INTO model_gap_analysis (model_name, ks_train, ks_oot, ks_gap, ks_gap_pct, auc_train, auc_oot, auc_gap, auc_gap_pct, gini_train, gini_oot, gini_gap, gini_gap_pct, overfit_risk, psi)
VALUES ('CatBoost', 0.37423, 0.34821, 0.02602, 6.95, 0.75325, 0.73539, 0.01786, 2.37, 50.65, 47.08, 3.57, 7.05, 'LOW', 0.000563);

-- RF: KS gap = 0.03453, gap% = 9.29 -> LOW
INSERT INTO model_gap_analysis (model_name, ks_train, ks_oot, ks_gap, ks_gap_pct, auc_train, auc_oot, auc_gap, auc_gap_pct, gini_train, gini_oot, gini_gap, gini_gap_pct, overfit_risk, psi)
VALUES ('RF', 0.37153, 0.33700, 0.03453, 9.29, 0.75121, 0.72778, 0.02343, 3.12, 50.24, 45.56, 4.68, 9.32, 'LOW', 0.001209);

-- Ensemble_Average: KS gap = 0.04436, gap% = 11.24 -> MODERATE
INSERT INTO model_gap_analysis (model_name, ks_train, ks_oot, ks_gap, ks_gap_pct, auc_train, auc_oot, auc_gap, auc_gap_pct, gini_train, gini_oot, gini_gap, gini_gap_pct, overfit_risk, psi)
VALUES ('Ensemble_Average', 0.39441, 0.35005, 0.04436, 11.24, 0.76611, 0.73677, 0.02934, 3.83, 53.22, 47.35, 5.87, 11.03, 'MODERATE', 0.000754);

COMMIT;
