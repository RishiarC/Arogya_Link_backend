import joblib
import pandas as pd
import os
import sys
from pathlib import Path
from django.conf import settings

# Path to the model
MODEL_PATH = os.path.join(settings.BASE_DIR, 'ML_model', 'arogya_link_ensemble_model2.pkl')
MODEL_LOAD_ERROR = None
_MODEL_CACHE = None
DEFAULT_FEATURE_NAMES = [
    'Age', 'Sex', 'Cholesterol', 'Heart Rate', 'Diabetes', 'Smoking', 'Obesity',
    'Alcohol Consumption', 'Exercise Hours Per Week', 'Previous Heart Problems',
    'Medication Use', 'Stress Level', 'Sedentary Hours Per Day', 'BMI',
    'Triglycerides', 'Physical Activity Days Per Week', 'Sleep Hours Per Day',
    'Systolic', 'Diastolic', 'Diet_Average', 'Diet_Healthy', 'Diet_Unhealthy'
]


def ensure_model_dependencies():
    try:
        import xgboost  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    version_tag = f"Python{sys.version_info.major}{sys.version_info.minor}"
    candidate_paths = [
        Path(sys.base_prefix) / "Lib" / "site-packages",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / version_tag / "Lib" / "site-packages",
        Path(settings.BASE_DIR) / "venv" / "Lib" / "site-packages",
    ]

    for path in candidate_paths:
        if not path.exists():
            continue
        if str(path) not in sys.path:
            sys.path.append(str(path))
        try:
            import xgboost  # noqa: F401
            return
        except ModuleNotFoundError:
            continue

def load_health_model():
    global MODEL_LOAD_ERROR, _MODEL_CACHE

    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    try:
        ensure_model_dependencies()
        _MODEL_CACHE = joblib.load(MODEL_PATH)
        MODEL_LOAD_ERROR = None
        return _MODEL_CACHE
    except Exception as e:
        MODEL_LOAD_ERROR = str(e)
        print(f"Error loading model: {e}")
        return None

def predict_heart_risk(features_dict):
    """
    Expects a dictionary with 22 features in the correct order.
    """
    model = load_health_model()
    if model is None:
        return "Model Error"
    
    # Define feature names as used in training
    feature_names = list(getattr(model, 'feature_names_in_', DEFAULT_FEATURE_NAMES))
    
    # Create DataFrame to ensure order matches model's feature_names_in_
    # In the Jupyter notebook, the training data was structured like this.
    try:
        missing_features = [name for name in feature_names if name not in features_dict]
        if missing_features:
            raise ValueError(f"Missing model features: {missing_features}")

        input_data = pd.DataFrame([features_dict], columns=feature_names)
        
        prediction = model.predict(input_data)[0]
        
        if prediction == 1:
            # If the specific heart rate or blood pressure is very high, mark as critical
            if features_dict.get('Heart Rate', 0) > 100 or features_dict.get('Systolic', 0) > 160:
                return 'Critical'
            return 'Medium'
        else:
            return 'Normal'
            
    except Exception as e:
        print(f"Prediction Error: {e}")
        return "Error"
