"""
Feature Correlation Analysis — Phase 1.4
Correlation matrix, VIF analysis, and feature clustering for the 59 selected features.

Usage: Run in OCI Data Science notebook after model training.
"""
import os
import json
from datetime import datetime

NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", "10"))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
DIAGNOSTIC_DIR = os.path.join(ARTIFACT_DIR, "diagnostic")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    SELECTED_FEATURES, NUM_FEATURES, CAT_FEATURES, TARGET,
    TRAIN_SAFRAS, LOCAL_DATA_PATH, GOLD_PATH,
)


def compute_correlation_matrix(df, features):
    """Compute correlation matrix for numerical features."""
    num_feats = [f for f in features if f not in CAT_FEATURES]
    corr_matrix = df[num_feats].corr()

    # Find highly correlated pairs
    high_corr_pairs = []
    for i in range(len(num_feats)):
        for j in range(i + 1, len(num_feats)):
            corr_val = corr_matrix.iloc[i, j]
            if abs(corr_val) > 0.80:
                high_corr_pairs.append({
                    "feature_1": num_feats[i],
                    "feature_2": num_feats[j],
                    "correlation": round(float(corr_val), 4),
                })

    high_corr_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    print(f"  Correlation matrix: {corr_matrix.shape}")
    print(f"  Pairs with |corr| > 0.80: {len(high_corr_pairs)}")
    if high_corr_pairs:
        print(f"\n  Top correlated pairs:")
        for pair in high_corr_pairs[:15]:
            print(f"    {pair['feature_1']:40s} x {pair['feature_2']:40s} = {pair['correlation']:.4f}")

    return corr_matrix, high_corr_pairs


def compute_vif(df, features, max_features=50):
    """Variance Inflation Factor for multicollinearity detection."""
    from sklearn.linear_model import LinearRegression
    from sklearn.impute import SimpleImputer

    num_feats = [f for f in features if f not in CAT_FEATURES][:max_features]

    # Impute missing values
    imputer = SimpleImputer(strategy="median")
    X = pd.DataFrame(
        imputer.fit_transform(df[num_feats]),
        columns=num_feats,
    )

    vif_data = []
    for i, feat in enumerate(num_feats):
        y = X[feat].values
        X_others = X.drop(columns=[feat]).values

        if X_others.shape[1] == 0:
            continue

        lr = LinearRegression()
        lr.fit(X_others, y)
        r_squared = lr.score(X_others, y)
        vif = 1 / (1 - r_squared) if r_squared < 1.0 else float("inf")

        vif_data.append({
            "feature": feat,
            "vif": round(float(vif), 2),
            "r_squared": round(float(r_squared), 4),
        })

    vif_df = pd.DataFrame(vif_data).sort_values("vif", ascending=False)

    high_vif = vif_df[vif_df["vif"] > 10]
    print(f"\n  VIF Analysis:")
    print(f"    Features with VIF > 10 (high multicollinearity): {len(high_vif)}")
    print(f"    Features with VIF > 5: {(vif_df['vif'] > 5).sum()}")

    if len(high_vif) > 0:
        print(f"\n    High VIF features:")
        print(high_vif.head(15).to_string(index=False))

    return vif_df


def cluster_features(df, features, n_clusters=8):
    """Hierarchical clustering of features to identify groups."""
    from sklearn.impute import SimpleImputer
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform

    num_feats = [f for f in features if f not in CAT_FEATURES]

    imputer = SimpleImputer(strategy="median")
    X = pd.DataFrame(
        imputer.fit_transform(df[num_feats]),
        columns=num_feats,
    )

    # Use correlation distance
    corr = X.corr().values
    # Ensure symmetric and handle numerical issues
    corr = (corr + corr.T) / 2
    np.fill_diagonal(corr, 1.0)
    corr = np.clip(corr, -1, 1)

    distance = 1 - np.abs(corr)
    np.fill_diagonal(distance, 0)
    distance = np.clip(distance, 0, None)

    # Condensed distance matrix
    condensed = squareform(distance, checks=False)

    linkage_matrix = linkage(condensed, method="ward")
    clusters = fcluster(linkage_matrix, t=n_clusters, criterion="maxclust")

    cluster_map = {}
    for feat, cluster_id in zip(num_feats, clusters):
        cluster_id = int(cluster_id)
        if cluster_id not in cluster_map:
            cluster_map[cluster_id] = []
        cluster_map[cluster_id].append(feat)

    print(f"\n  Feature Clustering ({n_clusters} clusters):")
    for cid in sorted(cluster_map.keys()):
        members = cluster_map[cid]
        # Identify domain from prefixes
        domains = set()
        for m in members:
            if m.startswith("REC_"):
                domains.add("REC")
            elif m.startswith("PAG_"):
                domains.add("PAG")
            elif m.startswith("FAT_"):
                domains.add("FAT")
            else:
                domains.add("OTHER")
        print(f"    Cluster {cid} ({len(members)} features, domains={domains}):")
        for m in members[:5]:
            print(f"      - {m}")
        if len(members) > 5:
            print(f"      ... and {len(members) - 5} more")

    # Identify cross-domain clusters (interaction candidates)
    cross_domain = {
        cid: members for cid, members in cluster_map.items()
        if len(set(
            "REC" if m.startswith("REC_") else
            "PAG" if m.startswith("PAG_") else
            "FAT" if m.startswith("FAT_") else "OTHER"
            for m in members
        )) > 1
    }

    print(f"\n  Cross-domain clusters (interaction candidates): {len(cross_domain)}")

    return cluster_map, cross_domain


def run_feature_correlation():
    """Full feature correlation analysis."""
    import pyarrow.parquet as pq

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("DIAGNOSTIC: Feature Correlation")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    # Load data (train only)
    columns_to_load = SELECTED_FEATURES + [TARGET, "SAFRA"]
    if os.path.exists(LOCAL_DATA_PATH):
        table = pq.read_table(LOCAL_DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(GOLD_PATH, columns=columns_to_load)

    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS)].copy()
    print(f"[DATA] Training data: {len(df_train):,} rows")

    # 1. Correlation matrix
    print("\n" + "-" * 70)
    print("1. CORRELATION MATRIX")
    print("-" * 70)

    corr_matrix, high_corr_pairs = compute_correlation_matrix(df_train, SELECTED_FEATURES)

    # 2. VIF analysis
    print("\n" + "-" * 70)
    print("2. VIF ANALYSIS")
    print("-" * 70)

    vif_df = compute_vif(df_train, SELECTED_FEATURES)

    # 3. Feature clustering
    print("\n" + "-" * 70)
    print("3. FEATURE CLUSTERING")
    print("-" * 70)

    cluster_map, cross_domain = cluster_features(df_train, SELECTED_FEATURES)

    # Save
    os.makedirs(DIAGNOSTIC_DIR, exist_ok=True)

    corr_matrix.to_csv(os.path.join(DIAGNOSTIC_DIR, f"correlation_matrix_{run_id}.csv"))
    vif_df.to_csv(os.path.join(DIAGNOSTIC_DIR, f"vif_analysis_{run_id}.csv"), index=False)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "high_corr_pairs": high_corr_pairs[:20],
        "high_vif_features": vif_df[vif_df["vif"] > 10]["feature"].tolist(),
        "feature_clusters": {str(k): v for k, v in cluster_map.items()},
        "cross_domain_clusters": {str(k): v for k, v in cross_domain.items()},
        "interaction_candidates": [],
    }

    # Suggest interaction candidates from cross-domain clusters
    for cid, members in cross_domain.items():
        rec = [m for m in members if m.startswith("REC_")]
        pag = [m for m in members if m.startswith("PAG_")]
        fat = [m for m in members if m.startswith("FAT_")]
        if rec and pag:
            report["interaction_candidates"].append(f"{rec[0]} x {pag[0]}")
        if rec and fat:
            report["interaction_candidates"].append(f"{rec[0]} x {fat[0]}")
        if pag and fat:
            report["interaction_candidates"].append(f"{pag[0]} x {fat[0]}")

    with open(os.path.join(DIAGNOSTIC_DIR, f"feature_correlation_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n[SAVE] Correlation analysis saved to {DIAGNOSTIC_DIR}/")
    print(f"\n  Interaction candidates: {len(report['interaction_candidates'])}")
    for cand in report["interaction_candidates"]:
        print(f"    - {cand}")

    return report


if __name__ == "__main__":
    run_feature_correlation()
