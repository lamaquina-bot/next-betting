"""
Motor predictivo — carga modelo XGBoost y ejecuta predicciones.
Modelo usa 185 features pero las más importantes son odds-based.
Para features no disponibles, usa valores por defecto (mediana del training).
"""
import joblib
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

# Default values for features that can't be computed from DB data
# These are approximations - odds-based features are the most important
FEATURE_DEFAULTS = {
    "year": 2024, "month": 6, "day_of_week": 3, "is_weekend": 0,
    "home_form_goals": 1.3, "home_form_conceded": 1.1, "home_form_points": 1.4,
    "away_form_goals": 1.1, "away_form_conceded": 1.2, "away_form_points": 1.2,
    "form_points_diff": 0.2, "form_goals_diff": 0.2,
    "home_team_home_goals_avg_10": 1.4, "home_team_home_conceded_avg_10": 1.0,
    "home_team_home_points_avg_10": 1.5, "home_win_rate_10": 0.45,
    "home_win_rate_home_10": 0.50, "home_clean_sheet_rate_10": 0.25,
    "away_team_away_goals_avg_10": 1.1, "away_team_away_conceded_avg_10": 1.2,
    "away_team_away_points_avg_10": 1.2, "away_win_rate_10": 0.30,
    "away_win_rate_away_10": 0.28, "away_clean_sheet_rate_10": 0.22,
    "home_streak": 0, "away_streak": 0, "home_streak_abs": 0, "away_streak_abs": 0,
    "home_goals_momentum_5": 0, "home_conceded_momentum_5": 0,
    "away_goals_momentum_5": 0, "away_conceded_momentum_5": 0,
    "home_xg_form": 1.3, "away_xg_form": 1.1, "home_xa_form": 1.1, "away_xa_form": 1.2,
    "home_win_loss_ratio_20": 1.0, "away_win_loss_ratio_20": 0.8,
    "quarter": 2, "day_of_year": 150, "day_of_year_sin": 0.5, "day_of_year_cos": 0.5,
    "week_of_year": 25, "month_sin": 0.0, "month_cos": 1.0,
    "day_of_week_sin": 0.0, "day_of_week_cos": 1.0,
    "season_phase": 0.5, "is_season_start": 0, "is_season_mid": 1, "is_season_end": 0,
    "home_days_rest": 5, "away_days_rest": 5, "home_well_rest": 1, "away_well_rest": 1,
    "home_fatigue": 0, "away_fatigue": 0,
    "h2h_home_wins_5": 2, "h2h_away_wins_5": 1, "h2h_draws_5": 2,
    "h2h_total_goals_5": 8, "h2h_home_wins_3": 1, "h2h_away_wins_3": 1, "h2h_matches_count": 5,
    "form_points_diff_expanded": 0.2, "form_goals_diff_expanded": 0.2,
    "form_conceded_diff": 0, "streak_diff": 0, "streak_abs_diff": 0,
    "momentum_goals_diff": 0, "rest_diff": 0,
    "win_rate_home_away_diff": 0.22, "win_rate_diff": 0.15,
    "form_points_diff_10": 0.2, "goal_avg_diff": 0.3,
    "points_ratio": 1.17, "goals_ratio": 1.27, "win_rate_ratio": 1.5,
    "home_efficiency": 0.5, "away_efficiency": 0.4, "efficiency_diff": 0.1,
    "form_x_odds_home": 1.0, "form_x_odds_away": 1.0,
    "winrate_x_odds_home": 1.0, "winrate_x_odds_away": 1.0,
    "form_odds_discrepancy_home": 0, "form_odds_discrepancy_away": 0,
    "home_points_momentum": 0, "away_points_momentum": 0, "momentum_diff": 0,
    "home_goals_std_10": 1.0, "away_goals_std_10": 1.0,
    "home_consistency": 0.5, "away_consistency": 0.5,
    "h2h_home_dominance": 0.5, "h2h_win_ratio": 0.5,
    "home_strength_score": 0.5, "away_strength_score": 0.4, "strength_diff": 0.1,
    "match_quality": 0.5, "match_predictability": 0.5,
    "is_balanced_match": 0, "is_clear_favorite": 0,
    "expected_high_scoring": 0, "expected_low_scoring": 0,
    "home_goals_trend": 0, "away_goals_trend": 0,
    "home_momentum": 0, "away_momentum": 0,
    "home_cluster": 1, "away_cluster": 1, "cluster_diff": 0,
    "home_FRic": 0.5, "home_FEve": 0.5, "home_FDiv": 0.5, "home_FDis": 0.5,
    "away_FRic": 0.5, "away_FEve": 0.5, "away_FDiv": 0.5, "away_FDis": 0.5,
    "FRic_diff": 0, "FEve_diff": 0, "FDiv_diff": 0, "FDis_diff": 0,
    "home_base_offensive_rating": 0.5, "home_base_defensive_rating": 0.5,
    "home_base_possession_style": 0.5, "home_base_attacking_intensity": 0.5,
    "home_base_set_piece_efficiency": 0.5,
    "away_base_offensive_rating": 0.4, "away_base_defensive_rating": 0.5,
    "away_base_possession_style": 0.5, "away_base_attacking_intensity": 0.4,
    "away_base_set_piece_efficiency": 0.5,
    "home_observed_goals_scored": 1.3, "home_observed_goals_conceded": 1.0,
    "home_observed_win_rate": 0.45, "home_observed_point_efficiency": 1.4,
    "away_observed_goals_scored": 1.1, "away_observed_goals_conceded": 1.2,
    "away_observed_win_rate": 0.30, "away_observed_point_efficiency": 1.2,
    "home_gp_goals_correlation": 0.5, "home_gp_efficiency_gap": 0,
    "home_gp_consistency_score": 0.5, "home_gp_adaptability": 0.5,
    "away_gp_goals_correlation": 0.5, "away_gp_efficiency_gap": 0,
    "away_gp_consistency_score": 0.5, "away_gp_adaptability": 0.5,
    "form_x_strength": 0.5, "form_x_strength_away": 0.4,
    "odds_x_efficiency": 0.5, "odds_x_efficiency_away": 0.4,
    "context_x_performance": 0.5, "context_x_performance_away": 0.4,
    "attack_defense_ratio": 1.0, "attack_defense_ratio_away": 0.8,
    "efficiency_ratio": 1.25, "dominance_index": 0.1,
    "compound_momentum": 0, "compound_momentum_away": 0,
    "trend_acceleration": 0, "pressure_index": 0,
    "fatigue_score": 0, "fatigue_score_away": 0,
    "home_advantage_amplified": 0.5,
    "distance_to_centroid": 0.5, "cluster_representativeness": 0.5,
    "training_weight": 1.0,
}


class Predictor:
    def __init__(self):
        self.model = None
        self.label_encoder = None
        self.feature_names = None
        self.model_version = "not-loaded"
        self._loaded = False

    def load_model(self, model_path: str = None):
        """Cargar modelo desde archivo joblib (dict con model, label_encoder, feature_names)"""
        path = Path(model_path or settings.model_path)
        if not path.exists():
            logger.warning(f"[Predictor] Modelo no encontrado en {path}")
            return

        try:
            artifact = joblib.load(path)
            if isinstance(artifact, dict):
                self.model = artifact["model"]
                self.label_encoder = artifact.get("label_encoder")
                self.feature_names = artifact.get("feature_names", [])
                self.model_version = path.stem
            else:
                self.model = artifact
                self.model_version = path.stem
            self._loaded = True
            logger.info(f"[Predictor] Modelo cargado: {self.model_version}, {len(self.feature_names)} features")
        except Exception as e:
            logger.error(f"[Predictor] Error cargando modelo: {e}")

    def build_features(self, avg_home_odds: float, avg_draw_odds: float, avg_away_odds: float,
                       match_date: datetime = None) -> np.ndarray:
        """Construir vector de features desde odds disponibles + defaults."""
        if match_date is None:
            match_date = datetime.utcnow()

        # Compute odds-based features (the most important ones)
        implied_home = 1.0 / avg_home_odds if avg_home_odds > 0 else 0.33
        implied_draw = 1.0 / avg_draw_odds if avg_draw_odds > 0 else 0.33
        implied_away = 1.0 / avg_away_odds if avg_away_odds > 0 else 0.33

        total_implied = implied_home + implied_draw + implied_away
        margin = total_implied - 1.0

        # Normalize to remove margin
        prob_home_norm = implied_home / total_implied
        prob_draw_norm = implied_draw / total_implied
        prob_away_norm = implied_away / total_implied

        prob_diff = abs(prob_home_norm - prob_away_norm)
        favorite_is_home = 1.0 if prob_home_norm > prob_away_norm else 0.0

        # Start with defaults
        features = {}
        for fname in self.feature_names:
            features[fname] = FEATURE_DEFAULTS.get(fname, 0.0)

        # Override with computed values
        features.update({
            "year": match_date.year,
            "month": match_date.month,
            "day_of_week": match_date.weekday(),
            "is_weekend": 1 if match_date.weekday() >= 5 else 0,
            "avg_odds_home": avg_home_odds,
            "avg_odds_draw": avg_draw_odds,
            "avg_odds_away": avg_away_odds,
            "prob_home_norm": prob_home_norm,
            "prob_draw_norm": prob_draw_norm,
            "prob_away_norm": prob_away_norm,
            "prob_diff": prob_diff,
            "bookmaker_margin": margin,
            "favorite_is_home": favorite_is_home,
            "implied_prob_home": implied_home,
            "implied_prob_vs_model": 0,  # can't compute without model
            "value_bet_score": 0,
        })

        # Build array in correct order
        return np.array([features.get(f, 0.0) for f in self.feature_names], dtype=np.float32)

    def predict(self, avg_home_odds: float, avg_draw_odds: float, avg_away_odds: float,
                match_date: datetime = None) -> dict:
        """Ejecutar predicción sobre odds de un partido."""
        if not self._loaded or self.model is None:
            # Fallback: usar implied probabilities
            h = 1.0 / avg_home_odds if avg_home_odds > 0 else 0.33
            d = 1.0 / avg_draw_odds if avg_draw_odds > 0 else 0.33
            a = 1.0 / avg_away_odds if avg_away_odds > 0 else 0.33
            total = h + d + a
            return {
                "home_prob": round(h / total, 4),
                "draw_prob": round(d / total, 4),
                "away_prob": round(a / total, 4),
                "confidence": 0.0,
                "model_version": "odds-implied-fallback",
            }

        features = self.build_features(avg_home_odds, avg_draw_odds, avg_away_odds, match_date)
        probs = self.model.predict_proba(features.reshape(1, -1))[0]

        # Label encoder: classes = ['A', 'D', 'H']
        # probs order matches: [A_prob, D_prob, H_prob]
        away_prob = float(probs[0])
        draw_prob = float(probs[1])
        home_prob = float(probs[2])

        return {
            "home_prob": round(home_prob, 4),
            "draw_prob": round(draw_prob, 4),
            "away_prob": round(away_prob, 4),
            "confidence": round(float(max(probs)), 4),
            "model_version": self.model_version,
        }

    def map_outcome(self, home_prob: float, draw_prob: float, away_prob: float) -> str:
        """Return the predicted outcome string."""
        probs = {"home": home_prob, "draw": draw_prob, "away": away_prob}
        return max(probs, key=probs.get)


predictor = Predictor()
