import pickle
import sys

try:
    with open("arogya_link_ensemble_model2.pkl", "rb") as f:
        model = pickle.load(f)

    print("Model Type:", type(model))

    # Try different common sklearn patterns to find feature names
    if hasattr(model, "feature_names_in_"):
        print("Features:", list(model.feature_names_in_))
    elif hasattr(model, "estimators_"):
        for est in model.estimators_:
            if hasattr(est, "feature_names_in_"):
                print("Features from estimator:", list(est.feature_names_in_))
                break
    elif hasattr(model, "steps"):  # Pipeline
        for name, step in model.steps:
            if hasattr(step, "feature_names_in_"):
                print("Features from pipeline step:", list(step.feature_names_in_))
                break

    if hasattr(model, "n_features_in_"):
        print("Number of features expected:", model.n_features_in_)

except Exception as e:
    print("Error:", str(e))
