"""Migrar CSVs históricos (184 archivos) a PostgreSQL"""
import os
import glob
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import sys

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://next:next@localhost:5433/next_betting")
DATA_DIR = os.getenv("DATA_DIR", "data/")

# Mapeo de columnas CSV → DB
COLUMN_MAP = {
    "Date": "match_date",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": "result",
    "B365H": "b365_home_odds",
    "B365D": "b365_draw_odds",
    "B365A": "b365_away_odds",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HY": "home_yellow",
    "AY": "away_yellow",
    "HR": "home_red",
    "AR": "away_red",
}


def migrate():
    engine = create_engine(DATABASE_URL.replace("+asyncpg", ""))

    csv_files = glob.glob(os.path.join(DATA_DIR, "**/*.csv"), recursive=True)
    print(f"[Migrate] Encontrados {len(csv_files)} archivos CSV")

    total_rows = 0
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, encoding="utf-8", on_bad_lines="skip")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_file, encoding="latin-1", on_bad_lines="skip")

        # Detectar liga del path
        parts = csv_file.replace("\\", "/").split("/")
        league = "unknown"
        for part in parts:
            if any(l in part.lower() for l in ["premier", "laliga", "la_liga", "serie", "bundes", "ligue", "champions"]):
                league = part
                break

        # Filtrar columnas que existen
        existing_cols = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
        if not existing_cols:
            continue

        df_filtered = df[list(existing_cols.keys())].rename(columns=existing_cols)
        df_filtered["league"] = league
        df_filtered["source_file"] = os.path.basename(csv_file)

        # Insertar a DB
        try:
            df_filtered.to_sql("historical_matches", engine, if_exists="append", index=False)
            total_rows += len(df_filtered)
            print(f"  ✅ {os.path.basename(csv_file)}: {len(df_filtered)} filas")
        except Exception as e:
            print(f"  ❌ {os.path.basename(csv_file)}: {e}")

    print(f"\n[Migrate] Total: {total_rows} filas migradas desde {len(csv_files)} archivos")

    # Crear índices
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_hm_league ON historical_matches(league)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_hm_date ON historical_matches(match_date)"))
        conn.commit()
    print("[Migrate] Índices creados ✅")


if __name__ == "__main__":
    migrate()
