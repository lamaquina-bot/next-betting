"""Kelly Criterion — cálculo de tamaño de apuesta óptimo"""


def calculate_stake(prob: float, odds: float, bankroll: float, fraction: float = 0.25) -> dict:
    """
    Calcular stake usando Kelly Criterion fraccional.
    
    f* = (bp - q) / b
    donde b = odds - 1, p = prob, q = 1 - p
    fraction = 0.25 (Quarter Kelly para reducir varianza)
    
    Retorna dict con stake, kelly_full, kelly_fraction y si es rentable.
    """
    if prob <= 0 or odds <= 1 or bankroll <= 0:
        return {"stake": 0, "kelly_full": 0, "kelly_fraction": 0, "profitable": False}

    b = odds - 1  # Ganancia neta por unidad apostada
    q = 1 - prob
    kelly_full = (b * prob - q) / b

    if kelly_full <= 0:
        return {"stake": 0, "kelly_full": round(kelly_full, 4), "kelly_fraction": 0, "profitable": False}

    kelly_fraction = kelly_full * fraction
    stake = round(bankroll * kelly_fraction, 2)

    return {
        "stake": stake,
        "kelly_full": round(kelly_full, 4),
        "kelly_fraction": round(kelly_fraction, 4),
        "profitable": True,
        "bankroll": bankroll,
    }
