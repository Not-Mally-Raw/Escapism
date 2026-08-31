"""
Lightweight treatment-effect modeling for revenue recovery actions.

This is a deliberately small T-learner-style implementation using sklearn
pipelines already available in the project environment. It estimates
P(recovery | state, action) per logged action and returns CATE against NOOP.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import joblib
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier

from src.core.models import MandateStateRecord
from src.core.types import ActionType
from src.ml.features import features_list_to_array, extract_features
from src.ml.pipeline import build_recovery_pipeline

NOOP_ACTION = "NOOP"
UPLIFT_ACTIONS = [
    NOOP_ACTION,
    ActionType.SILENT_RETRY.value,
    ActionType.PIN_PROMPTED_RETRY.value,
    ActionType.SMS_NUDGE.value,
    ActionType.PAYMENT_LINK.value,
    ActionType.WHATSAPP_NUDGE.value,
    ActionType.RE_MANDATE_FLOW.value,
    ActionType.COOLDOWN_WAIT.value,
]

_MODEL_PATH = Path(__file__).parent / "models" / "uplift_t_learner.joblib"
_METADATA_PATH = Path(__file__).parent / "models" / "uplift_metadata.json"
_CACHED_UPLIFT: Optional[Dict[str, Any]] = None


def _make_base_pipeline(random_state: int = 42):
    pipe = build_recovery_pipeline(C=1.0, class_weight=None, random_state=random_state)
    pipe.steps[-1] = (
        "classifier",
        GradientBoostingClassifier(random_state=random_state, n_estimators=80, max_depth=3),
    )
    return pipe


def _fit_action_model(features: list[dict[str, Any]], outcomes: list[int], random_state: int):
    X = features_list_to_array(features)
    y = np.array(outcomes, dtype=int)
    if len(np.unique(y)) < 2:
        model = build_recovery_pipeline(C=1.0, class_weight=None, random_state=random_state)
        model.steps[-1] = ("classifier", DummyClassifier(strategy="constant", constant=int(y[0]) if len(y) else 0))
    else:
        model = _make_base_pipeline(random_state=random_state)
    model.fit(X, y)
    return model


def load_causal_dataset(data_path: Path) -> list[dict[str, Any]]:
    rows = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def train_uplift_model(
    data_path: Path = Path("data/causal_batch_5000.jsonl"),
    model_output_path: Path = _MODEL_PATH,
    metadata_output_path: Path = _METADATA_PATH,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Train one outcome model per logged action and store PEHE against the known DGP.
    """
    rows = load_causal_dataset(data_path)
    by_action: Dict[str, list[tuple[dict[str, Any], int]]] = {a: [] for a in UPLIFT_ACTIONS}
    true_cates: list[dict[str, float]] = []
    states: list[MandateStateRecord] = []

    for row in rows:
        action = row["observed_action"]
        if action not in by_action:
            continue
        feat = extract_features(row["state"])
        by_action[action].append((feat, int(bool(row["observed_outcome"]))))
        true_cates.append(row.get("true_cate", {}))
        states.append(MandateStateRecord(**row["state"]))

    models: Dict[str, Any] = {}
    support: Dict[str, int] = {}
    for action, action_rows in by_action.items():
        if not action_rows:
            continue
        features, outcomes = zip(*action_rows)
        support[action] = len(action_rows)
        models[action] = _fit_action_model(list(features), list(outcomes), random_state=random_state)

    pehe_by_action: Dict[str, float] = {}
    for action in UPLIFT_ACTIONS:
        if action == NOOP_ACTION or action not in models or NOOP_ACTION not in models:
            continue
        errors = []
        for state, cate_dict in zip(states, true_cates):
            pred = predict_treatment_effect(state, ActionType(action), model_bundle={"models": models})
            truth = float(cate_dict.get(action, 0.0))
            errors.append((pred - truth) ** 2)
        pehe_by_action[action] = float(np.sqrt(np.mean(errors))) if errors else 0.0

    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {"models": models, "actions": UPLIFT_ACTIONS, "noop_action": NOOP_ACTION}
    joblib.dump(bundle, model_output_path)

    metadata = {
        "model_name": "SklearnTLearnerRecoveryUplift",
        "training_data": str(data_path),
        "total_rows": len(rows),
        "action_support": support,
        "pehe_by_action": pehe_by_action,
        "method": "One sklearn outcome model per logged action; CATE(action)=P(action)-P(NOOP).",
    }
    with open(metadata_output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    reset_uplift_cache()
    return metadata


def reset_uplift_cache() -> None:
    global _CACHED_UPLIFT
    _CACHED_UPLIFT = None


def get_uplift_model(model_path: Optional[Path] = None) -> Dict[str, Any]:
    global _CACHED_UPLIFT
    path = model_path or _MODEL_PATH
    if not path.exists():
        raise FileNotFoundError(f"Uplift model artifact not found at {path}")
    if _CACHED_UPLIFT is None or model_path is not None:
        loaded = joblib.load(path)
        if model_path is None:
            _CACHED_UPLIFT = loaded
        return loaded
    return _CACHED_UPLIFT


def uplift_model_available(model_path: Optional[Path] = None) -> bool:
    return (model_path or _MODEL_PATH).exists()


def _predict_action_probability(model: Any, state: MandateStateRecord) -> float:
    X = features_list_to_array([extract_features(state)])
    if hasattr(model, "predict_proba"):
        return float(model.predict_proba(X)[0, 1])
    return float(model.predict(X)[0])


def predict_treatment_effect(
    state: MandateStateRecord,
    action: ActionType,
    model_path: Optional[Path] = None,
    model_bundle: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Return estimated CATE(state, action) against NOOP. Missing artifacts raise
    FileNotFoundError so callers can fall back explicitly.
    """
    action_name = action.value
    bundle = model_bundle or get_uplift_model(model_path)
    models = bundle["models"]
    if action_name not in models or NOOP_ACTION not in models:
        raise KeyError(f"Uplift model missing action arm: {action_name}")
    p_action = _predict_action_probability(models[action_name], state)
    p_noop = _predict_action_probability(models[NOOP_ACTION], state)
    return max(-1.0, min(1.0, p_action - p_noop))


if __name__ == "__main__":
    metadata = train_uplift_model()
    print("=================================================================")
    print("UPLIFT MODEL TRAINING COMPLETE")
    print("=================================================================")
    print(json.dumps(metadata, indent=2))
