"""Alertas via Telegram bot (con protección de token - Fix 6)"""
import logging
import re
from datetime import datetime

import httpx
from app.config import settings

logger = logging.getLogger("next.alerts")


def _validar_token(token: str) -> bool:
    """Validar que el token de Telegram tenga formato correcto (número:alphanumeric)."""
    # Los tokens de Telegram Bot siguen el formato <número>:<35 caracteres alfanuméricos>
    patron = re.compile(r"^\d{8,10}:[A-Za-z0-9_-]{35}$")
    return bool(patron.match(token))


async def send_telegram(message: str, chat_id: str = None, bot_token: str = None) -> bool:
    """Enviar mensaje via Telegram bot API con validación y auditoría."""
    token = bot_token or settings.telegram_bot_token
    chat = chat_id or settings.telegram_chat_id

    if not token or not chat:
        logger.warning("Telegram no configurado (falta token o chat_id)")
        return False

    # Fix 6 - Validar formato del token
    if not _validar_token(token):
        logger.error(f"Token de Telegram con formato inválido (no coincide patrón digit:alphanumeric)")
        return False

    # Auditoría: registrar uso del token (sin exponerlo)
    logger.info(f"Telegram API llamada - chat_id={chat} - ts={datetime.utcnow().isoformat()}")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram mensaje enviado exitosamente")
            else:
                logger.warning(f"Telegram API respondió {resp.status_code}: {resp.text[:200]}")
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Error enviando Telegram: {e}")
        return False


def format_pick_message(value_bet: dict) -> str:
    """Formatear value bet para notificación Telegram"""
    emoji = "🟢" if value_bet.get("edge", 0) > 0.10 else "🟡"
    return (
        f"{emoji} <b>NEXT - Value Bet Detectada</b>\n\n"
        f"⚽ {value_bet.get('fixture', 'N/A')}\n"
        f"🎯 Apuesta: <b>{value_bet.get('outcome', 'N/A').upper()}</b>\n"
        f"📊 Prob. modelo: {value_bet.get('model_prob', 0)*100:.1f}%\n"
        f"💰 Cuota mercado: {value_bet.get('market_odds', 0):.2f}\n"
        f"📈 Edge: <b>{value_bet.get('edge_pct', 0):.1f}%</b>\n"
        f"💵 Stake sugerido: ${value_bet.get('stake', 0):,.0f}\n"
        f"🕐 {value_bet.get('detected_at', 'N/A')}"
    )
