from __future__ import annotations

from typing import Any

import numpy as np


def build_agent2_model_comparison(
    *,
    contracts: Any,
    scores: Any,
    deviation_threshold: float,
) -> Any:
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import IsolationForest
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    frame = contracts[
        [
            "contract_key_canon",
            "buyer_name",
            "supplier_name",
            "procedure",
            "estimated_value_eur",
            "awarded_value_eur",
            "publication_date",
            "award_date",
            "resolution_days",
        ]
    ].copy()
    frame = frame.merge(
        scores[["contract_key_canon", "risk_score", "flags_count", "top_flags"]],
        on="contract_key_canon",
        how="left",
    )
    frame["rule_positive"] = frame["flags_count"].fillna(0).gt(0).astype(int)
    frame["deviation_ratio"] = np.where(
        frame["estimated_value_eur"].fillna(0) > 0,
        (frame["awarded_value_eur"] - frame["estimated_value_eur"]) / frame["estimated_value_eur"],
        np.nan,
    )
    frame["has_supplier_name"] = frame["supplier_name"].astype("string").fillna("").str.strip().ne("")
    frame["has_buyer_name"] = frame["buyer_name"].astype("string").fillna("").str.strip().ne("")
    frame["has_estimated_value"] = frame["estimated_value_eur"].notna() & (frame["estimated_value_eur"] > 0)
    frame["has_awarded_value"] = frame["awarded_value_eur"].notna()
    frame["has_resolution_days"] = pd.to_numeric(frame["resolution_days"], errors="coerce").notna()
    frame["resolution_days"] = pd.to_numeric(frame["resolution_days"], errors="coerce")
    frame["estimated_value_eur"] = pd.to_numeric(frame["estimated_value_eur"], errors="coerce")
    frame["awarded_value_eur"] = pd.to_numeric(frame["awarded_value_eur"], errors="coerce")

    if frame.empty:
        return pd.DataFrame(
            columns=[
                "contract_key_canon",
                "rule_score",
                "rule_flags_count",
                "rule_positive",
                "iforest_anomaly_score",
                "iforest_anomaly_flag",
                "pu_probability",
                "pu_label",
                "agreement_iforest_rule",
                "agreement_pu_rule",
            ]
        )

    numeric_features = [
        "estimated_value_eur",
        "awarded_value_eur",
        "deviation_ratio",
        "resolution_days",
    ]
    categorical_features = ["procedure"]
    boolean_features = [
        "has_supplier_name",
        "has_buyer_name",
        "has_estimated_value",
        "has_awarded_value",
        "has_resolution_days",
    ]
    model_frame = frame[numeric_features + categorical_features + boolean_features].copy()

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_features,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            ),
            (
                "bool",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                    ]
                ),
                boolean_features,
            ),
        ],
        remainder="drop",
    )

    comparison = pd.DataFrame(
        {
            "contract_key_canon": frame["contract_key_canon"].astype("string"),
            "rule_score": frame["risk_score"].fillna(0.0),
            "rule_flags_count": frame["flags_count"].fillna(0).astype(int),
            "rule_positive": frame["rule_positive"].astype(int),
        }
    )

    anomaly_share = float(frame["rule_positive"].mean()) if len(frame) else 0.0
    contamination = min(max(anomaly_share or 0.05, 0.01), 0.20)
    iforest = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            (
                "model",
                IsolationForest(
                    n_estimators=200,
                    contamination=contamination,
                    random_state=42,
                ),
            ),
        ]
    )
    iforest.fit(model_frame)
    comparison["iforest_anomaly_score"] = -iforest.decision_function(model_frame)
    comparison["iforest_anomaly_flag"] = iforest.predict(model_frame) == -1

    pu_positive = frame["rule_positive"].astype(int)
    if pu_positive.nunique() < 2 or pu_positive.sum() < 2:
        comparison["pu_probability"] = pu_positive.astype(float)
        comparison["pu_label"] = pu_positive.astype(bool)
    else:
        pu_model = Pipeline(
            steps=[
                ("preprocess", preprocessor),
                (
                    "model",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        solver="liblinear",
                        random_state=42,
                    ),
                ),
            ]
        )
        pu_model.fit(model_frame, pu_positive)
        positive_prob = pu_model.predict_proba(model_frame)[:, 1]
        positive_reference = pu_model.predict_proba(model_frame[pu_positive.eq(1)])[:, 1]
        c_value = float(np.mean(positive_reference)) if len(positive_reference) else 1.0
        c_value = c_value if c_value > 0 else 1.0
        pu_probability = np.clip(positive_prob / c_value, 0.0, 1.0)
        comparison["pu_probability"] = pu_probability
        comparison["pu_label"] = comparison["pu_probability"] >= 0.5

    comparison["agreement_iforest_rule"] = (
        comparison["iforest_anomaly_flag"].astype(bool) == comparison["rule_positive"].astype(bool)
    )
    comparison["agreement_pu_rule"] = (
        comparison["pu_label"].astype(bool) == comparison["rule_positive"].astype(bool)
    )
    return comparison


def evaluate_agent2_model_comparison(comparison: Any) -> dict[str, Any]:
    import pandas as pd
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    frame = pd.DataFrame(comparison).copy()
    if frame.empty:
        return {
            "reference": "rule_positive",
            "rows": 0,
            "iforest": _empty_comparison_metrics(),
            "pu": _empty_comparison_metrics(),
        }

    y_true = frame["rule_positive"].astype(int)
    return {
        "reference": "rule_positive",
        "rows": int(len(frame)),
        "iforest": _comparison_metrics(
            y_true=y_true,
            y_pred=frame["iforest_anomaly_flag"].astype(int),
            y_score=frame["iforest_anomaly_score"],
        ),
        "pu": _comparison_metrics(
            y_true=y_true,
            y_pred=frame["pu_label"].astype(int),
            y_score=frame["pu_probability"],
        ),
    }


def _comparison_metrics(*, y_true: Any, y_pred: Any, y_score: Any) -> dict[str, Any]:
    import pandas as pd
    from sklearn.metrics import roc_auc_score

    truth = pd.Series(y_true).astype(int)
    pred = pd.Series(y_pred).astype(int)
    score = pd.Series(y_score)
    truth_array = truth.to_numpy()
    pred_array = pred.to_numpy()
    tp = int(((truth_array == 1) & (pred_array == 1)).sum())
    tn = int(((truth_array == 0) & (pred_array == 0)).sum())
    fp = int(((truth_array == 0) & (pred_array == 1)).sum())
    fn = int(((truth_array == 1) & (pred_array == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    tnr = tn / (tn + fp) if (tn + fp) else 0.0
    accuracy = (tp + tn) / len(truth_array) if len(truth_array) else 0.0
    balanced_accuracy = (recall + tnr) / 2.0 if len(truth_array) else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    metrics = {
        "support": int(len(truth)),
        "positive_support": int(truth.sum()),
        "predicted_positive": int(pred.sum()),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
        "accuracy": round(float(accuracy), 4),
        "balanced_accuracy": round(float(balanced_accuracy), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": None,
    }
    try:
        if truth.nunique() > 1 and pd.Series(score).nunique(dropna=True) > 1:
            metrics["roc_auc"] = round(float(roc_auc_score(truth, score)), 4)
    except Exception:
        metrics["roc_auc"] = None
    return metrics


def _empty_comparison_metrics() -> dict[str, Any]:
    return {
        "support": 0,
        "positive_support": 0,
        "predicted_positive": 0,
        "tp": 0,
        "fp": 0,
        "tn": 0,
        "fn": 0,
        "accuracy": 0.0,
        "balanced_accuracy": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "roc_auc": None,
    }
