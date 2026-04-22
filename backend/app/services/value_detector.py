"""Detección de value bets — compara probabilidad del modelo vs cuotas del mercado"""
from datetime import datetime


def detect_value_bets(predictions: list[dict], odds: list[dict], min_edge: float = 0.05) -> list[dict]:
    """
    Detectar value bets comparando probabilidad modelo vs cuotas mercado.
    edge = (prob × cuota) - 1. Si edge > min_edge → value bet.
    """
    value_bets = []

    for pred in predictions:
        fixture_id = pred.get("fixture_id")
        home_prob = pred.get("home_prob", 0)
        draw_prob = pred.get("draw_prob", 0)
        away_prob = pred.get("away_prob", 0)

        # Buscar odds para este fixture
        fixture_odds = [o for o in odds if o.get("fixture_id") == fixture_id]
        if not fixture_odds:
            continue

        for odd_entry in fixture_odds:
            home_odds = odd_entry.get("home_odds", 0)
            draw_odds = odd_entry.get("draw_odds", 0)
            away_odds = odd_entry.get("away_odds", 0)

            # Calcular edges
            outcomes = [
                ("home", home_prob, home_odds),
                ("draw", draw_prob, draw_odds),
                ("away", away_prob, away_odds),
            ]

            for outcome, prob, market_odds in outcomes:
                if prob > 0 and market_odds > 1:
                    edge = (prob * market_odds) - 1
                    if edge >= min_edge:
                        value_bets.append({
                            "fixture_id": fixture_id,
                            "outcome": outcome,
                            "model_prob": prob,
                            "market_odds": market_odds,
                            "edge": edge,
                            "edge_pct": round(edge * 100, 2),
                            "confidence": pred.get("confidence", 0),
                            "detected_at": datetime.now().isoformat(),
                        })

    # Ordenar por edge descendente
    value_bets.sort(key=lambda x: x["edge"], reverse=True)
    return value_bets
