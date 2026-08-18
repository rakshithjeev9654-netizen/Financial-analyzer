
import numpy as np
from sklearn.ensemble import IsolationForest

def _flatten(ratios):
    names=[]
    row=[]
    for cat, items in ratios.items():
        for r in items:
            if r["is_available"] if isinstance(r,dict) else r.is_available:
                names.append(r["name"])
                row.append(r["value"])
    return names,row

def detect_ratio_anomalies(ratios):
    # Unsupervised ML: detects unusual ratio combinations without fabricated labels.
    names, values = [], []
    for cat, items in ratios.items():
        for r in items:
            if r.is_available and r.value is not None:
                names.append(r.name); values.append(float(r.value))
    if len(values) < 4:
        return {
            "model":"Isolation Forest (unsupervised ML)",
            "status":"Insufficient data",
            "anomaly_score":None,
            "flagged_ratios":[],
            "explanation":"At least four available ratio observations are needed for a stable anomaly screen."
        }
    X = np.array(values).reshape(-1,1)
    model = IsolationForest(n_estimators=150, contamination="auto", random_state=42)
    pred = model.fit_predict(X)
    scores = model.decision_function(X)
    flagged=[names[i] for i,p in enumerate(pred) if p==-1]
    raw=float(np.mean(scores))
    # convert to an easy-to-read score where higher = more unusual
    anomaly_score=round(max(0,min(100,50-(raw*100))),1)
    status="Potential anomalies detected" if flagged else "No strong anomalies detected"
    return {
        "model":"Isolation Forest (unsupervised ML)",
        "status":status,
        "anomaly_score":anomaly_score,
        "flagged_ratios":flagged,
        "explanation":"Unsupervised outlier screening over the available ratio values; it does not predict default or investment returns."
    }
