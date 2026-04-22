"""Motor predictivo — carga modelo y ejecuta predicciones"""
import joblib
import numpy as np
from pathlib import Path
from app.config import settings


class Predictor:
    def __init__(self):
        self.model = None
        self.model_version = "unknown"

    def load_model(self, model_path: str = None):
        """Cargar modelo desde archivo pickle/joblib"""
        path = Path(model_path or settings.model_path)
        if path.exists():
            self.model = joblib.load(path)
            self.model_version = path.stem
            print(f"[Predictor] Modelo cargado: {self.model_version}")
        else:
            print(f"[Predictor] ⚠️ No se encontró modelo en {path}")

    def predict(self, features: np.ndarray) -> dict:
        """Ejecutar predicción sobre features de un partido"""
        if self.model is None:
            return {"home_prob": 0.33, "draw_prob": 0.33, "away_prob": 0.33, "confidence": 0.0}

        probs = self.model.predict_proba(features.reshape(1, -1))[0]

        return {
            "home_prob": float(probs[0]),
            "draw_prob": float(probs[1]),
            "away_prob": float(probs[2]),
            "confidence": float(max(probs)),
            "model_version": self.model_version,
        }


predictor = Predictor()
