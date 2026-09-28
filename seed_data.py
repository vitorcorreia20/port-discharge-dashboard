"""
seed_data.py — Gera o banco SQLite `porto.db` para análise de descarga de granel sólido (Agosto/2026).

Tabelas:
  - atracacoes(id_atracacao, navio, carga, toneladas_manifestadas, atracacao, inicio_descarga, fim_descarga, desatracacao)
  - viagens(id_viagem, id_atracacao, id_caminhao, transportadora, entrada_patio, saida_patio)
  - pesagens(id_pesagem, id_viagem, hora_tara, tara_kg, hora_bruto, peso_bruto_kg)

Views:
  - vw_kpi_prancha      : media t/h por atracacao
  - vw_kpi_progresso    : toneladas acumuladas vs manifestadas (% progresso)
  - vw_kpi_tempo_ciclo  : tempo medio no patio (min) por transportadora

Uso:
    python seed_data.py [--db porto.db] [--seed 42]
"""
from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "porto.db"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS vw_kpi_prancha;
DROP VIEW IF EXISTS vw_kpi_progresso;
DROP VIEW IF EXISTS vw_kpi_tempo_ciclo;
DROP TABLE IF EXISTS pesagens;
DROP TABLE IF EXISTS viagens;
DROP TABLE IF EXISTS atracacoes;

CREATE TABLE atracacoes (
    id_atracacao INTEGER PRIMARY KEY,
    navio TEXT NOT NULL,
    carga TEXT NOT NULL,
    toneladas_manifestadas REAL NOT NULL,
    atracacao TEXT NOT NULL,
    inicio_descarga TEXT NOT NULL,
    fim_descarga TEXT,
    desatracacao TEXT
);

CREATE TABLE viagens (
    id_viagem INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atracacao INTEGER NOT NULL REFERENCES atracacoes(id_atracacao),
    id_caminhao TEXT NOT NULL,
    transportadora TEXT NOT NULL,
    entrada_patio TEXT NOT NULL,
    saida_patio TEXT
);

CREATE TABLE pesagens (
    id_pesagem INTEGER PRIMARY KEY AUTOINCREMENT,
    id_viagem INTEGER NOT NULL REFERENCES viagens(id_viagem),
    hora_tara TEXT NOT NULL,
    tara_kg REAL NOT NULL,
    hora_bruto TEXT NOT NULL,
    peso_bruto_kg REAL NOT NULL
);
"""

# Views compativeis com SQLite. Consideram apenas pesagens validas
# (peso_bruto_kg > tara_kg AND tara_kg > 0) para nao distorcer os KPIs.
# As viagens invalidas continuam nas tabelas base e aparecem na auditoria do app.
VIEWS_SQL = """
CREATE VIEW vw_kpi_prancha AS
SELECT
    a.id_atracacao,
    a.navio,
    a.carga,
    a.toneladas_manifestadas,
    COUNT(p.id_pesagem) AS n_viagens_validas,
    ROUND(COALESCE(SUM((p.peso_bruto_kg - p.tara_kg) / 1000.0), 0), 2) AS total_descarregado_t,
    ROUND(
        (JULIANDAY(
            COALESCE(
                a.fim_descarga,
                (SELECT MAX(p2.hora_bruto)
                 FROM pesagens p2
                 JOIN viagens v2 ON v2.id_viagem = p2.id_viagem
                 WHERE v2.id_atracacao = a.id_atracacao)
            )
        ) - JULIANDAY(a.inicio_descarga)) * 24.0, 2
    ) AS horas_operacao,
    ROUND(
        COALESCE(SUM((p.peso_bruto_kg - p.tara_kg) / 1000.0), 0)
        / NULLIF((JULIANDAY(
            COALESCE(
                a.fim_descarga,
                (SELECT MAX(p2.hora_bruto)
                 FROM pesagens p2
                 JOIN viagens v2 ON v2.id_viagem = p2.id_viagem
                 WHERE v2.id_atracacao = a.id_atracacao)
            )
        ) - JULIANDAY(a.inicio_descarga)) * 24.0, 0),
    2) AS prancha_media_th
FROM atracacoes a
LEFT JOIN viagens v ON v.id_atracacao = a.id_atracacao
LEFT JOIN pesagens p ON p.id_viagem = v.id_viagem
    AND p.peso_bruto_kg > p.tara_kg
    AND p.tara_kg > 0
GROUP BY a.id_atracacao, a.navio, a.carga, a.toneladas_manifestadas,
         a.inicio_descarga, a.fim_descarga;

CREATE VIEW vw_kpi_progresso AS
SELECT
    a.id_atracacao,
    a.navio,
    a.toneladas_manifestadas,
    ROUND(COALESCE(SUM((p.peso_bruto_kg - p.tara_kg) / 1000.0), 0), 2) AS toneladas_acumuladas_t,
    ROUND(COALESCE(SUM((p.peso_bruto_kg - p.tara_kg) / 1000.0), 0) / NULLIF(a.toneladas_manifestadas, 0) * 100.0, 2)
        AS progresso_pct
FROM atracacoes a
LEFT JOIN viagens v ON v.id_atracacao = a.id_atracacao
LEFT JOIN pesagens p ON p.id_viagem = v.id_viagem
    AND p.peso_bruto_kg > p.tara_kg
    AND p.tara_kg > 0
GROUP BY a.id_atracacao, a.navio, a.toneladas_manifestadas;

CREATE VIEW vw_kpi_tempo_ciclo AS
SELECT
    v.transportadora,
    COUNT(*) AS n_viagens,
    ROUND(AVG((JULIANDAY(v.saida_patio) - JULIANDAY(v.entrada_patio)) * 1440.0), 1) AS tempo_medio_patio_min,
    ROUND(MIN((JULIANDAY(v.saida_patio) - JULIANDAY(v.entrada_patio)) * 1440.0), 1) AS tempo_minimo_min,
    ROUND(MAX((JULIANDAY(v.saida_patio) - JULIANDAY(v.entrada_patio)) * 1440.0), 1) AS tempo_maximo_min,
    SUM(CASE WHEN (JULIANDAY(v.saida_patio) - JULIANDAY(v.entrada_patio)) * 1440.0 > 120 THEN 1 ELSE 0 END)
        AS n_viagens_acima_120min
FROM viagens v
WHERE v.entrada_patio IS NOT NULL AND v.saida_patio IS NOT NULL
GROUP BY v.transportadora;
"""


def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def random_plate(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))
    digits = "".join(rng.choice("0123456789") for _ in range(4))
    return f"{letters}-{digits}"


def spread_datetimes(start: datetime, end: datetime, n: int, rng: random.Random) -> list[datetime]:
    """Distribui n datetimes ordenados entre start e end, com jitter operacional.

    Simula operacao ~06h-23h com picos de manha/tarde: gera timestamps uniformes
    e depois ordena. Simples, deterministico via rng e realista o suficiente.
    """
    total = (end - start).total_seconds()
    dts = []
    for _ in range(n):
        # concentra operacao no periodo diurno: rejeita madrugadas 00-05 com 70% prob.
        while True:
            offset = rng.random() * total
            dt = start + timedelta(seconds=offset)
            if 0 <= dt.hour <= 5 and rng.random() < 0.7:
                continue
            break
        dts.append(dt)
    dts.sort()
    # garante espacamento minimo de ~15 min entre caminhoes para evitar colisao total
    for i in range(1, len(dts)):
        if (dts[i] - dts[i - 1]).total_seconds() < 8 * 60:
            dts[i] = dts[i - 1] + timedelta(minutes=rng.randint(8, 25))
            if dts[i] > end:
                dts[i] = end - timedelta(minutes=rng.randint(5, 60))
    dts.sort()
    return dts


def build_viagem_times(
    base: datetime, transportadora: str, rng: random.Random
) -> tuple[datetime, datetime, datetime, datetime]:
    """Retorna (entrada_patio, hora_tara, hora_bruto, saida_patio)."""
    # Perfis medios de ciclo por transportadora (min no patio):
    # TransPorto = operacao enxuta | LogGranel = intermediaria | EcoCargas = gargalo.
    # Diferenciacao em duas alavancas: fila da balanca + tempo de carga no cais.
    if transportadora == "TransPorto":
        ciclo_alvo = rng.gauss(45, 9)
        espera_tara = rng.randint(4, 10)
        carga_cais = rng.randint(25, 50)
        espera_saida = rng.randint(3, 8)
    elif transportadora == "LogGranel":
        ciclo_alvo = rng.gauss(62, 10)
        espera_tara = rng.randint(6, 14)
        carga_cais = rng.randint(35, 65)
        espera_saida = rng.randint(5, 10)
    else:  # EcoCargas
        ciclo_alvo = rng.gauss(88, 15)
        espera_tara = rng.randint(8, 18)
        carga_cais = rng.randint(50, 85)
        espera_saida = rng.randint(6, 14)
    ciclo_alvo = max(20.0, ciclo_alvo)

    entrada = base
    hora_tara = entrada + timedelta(minutes=espera_tara)
    hora_bruto = hora_tara + timedelta(minutes=carga_cais)
    # ajusta saida para fechar o ciclo total sorteado
    decorrido = (hora_bruto - entrada).total_seconds() / 60 + espera_saida
    extra = max(0.0, ciclo_alvo - decorrido)
    saida = hora_bruto + timedelta(minutes=espera_saida + extra)
    return entrada, hora_tara, hora_bruto, saida


def seed_database(db_path: Path, rng_seed: int = 42) -> Path:
    rng = random.Random(rng_seed)

    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.executescript(SCHEMA_SQL)

    # ------------------------------------------------------------------
    # 1) Atracacoes — Agosto/2026
    # Volumes propositadamente em escala de "lote piloto" para que
    # ~90 viagens (~30 t cada) gerem curvas de progresso legiveis.
    # Em operacao real, o manifesto seria de dezenas de milhares de t.
    # ------------------------------------------------------------------
    atracacoes = [
        (
            1, "MV Vale Brasil", "Minerio de Ferro", 1650.0,
            "2026-08-04 08:00:00", "2026-08-04 14:00:00",
            "2026-08-10 22:00:00", "2026-08-11 02:00:00",
        ),
        (
            2, "MV Ore Amazon", "Minerio de Ferro", 3800.0,
            "2026-08-14 06:00:00", "2026-08-14 12:00:00",
            None, None,  # em operacao
        ),
    ]
    cur.executemany(
        """INSERT INTO atracacoes
           (id_atracacao, navio, carga, toneladas_manifestadas, atracacao,
            inicio_descarga, fim_descarga, desatracacao)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        atracacoes,
    )

    transportadoras = ["TransPorto", "LogGranel", "EcoCargas"]
    caminhoes_por_transportadora: dict[str, list[str]] = {
        t: [random_plate(rng) for _ in range(12)] for t in transportadoras
    }

    viagens_rows: list[tuple] = []
    pesagens_rows: list[tuple] = []

    plan = [
        # (id_atracacao, n_viagens, inicio_janela, fim_janela)
        (1, 48, datetime(2026, 8, 4, 14, 0, 0), datetime(2026, 8, 10, 21, 0, 0)),
        (2, 42, datetime(2026, 8, 14, 12, 0, 0), datetime(2026, 8, 20, 18, 0, 0)),
    ]

    id_viagem_seq = 1
    # guarda ids para aplicar anomalias depois (por indice global da lista)
    for id_atracacao, n, ini, fim in plan:
        bases = spread_datetimes(ini, fim, n, rng)
        for base in bases:
            # sorteio ponderado: TransPorto 40% / LogGranel 35% / EcoCargas 25%
            r = rng.random()
            transportadora = "TransPorto" if r < 0.40 else ("LogGranel" if r < 0.75 else "EcoCargas")
            caminhao = rng.choice(caminhoes_por_transportadora[transportadora])
            entrada, hora_tara, hora_bruto, saida = build_viagem_times(base, transportadora, rng)

            tara = round(rng.gauss(15200, 900), 1)
            tara = max(12500.0, min(tara, 18000.0))
            liquido = max(24000.0, rng.gauss(31000, 2200))  # ~31 t por viagem
            bruto = round(tara + liquido, 1)

            viagens_rows.append((id_viagem_seq, id_atracacao, caminhao, transportadora, fmt(entrada), fmt(saida)))
            pesagens_rows.append((id_viagem_seq, fmt(hora_tara), tara, fmt(hora_bruto), bruto))
            id_viagem_seq += 1

    # ------------------------------------------------------------------
    # 2) Anomalias reais (3 casos) — para testar resiliencia / auditoria
    # ------------------------------------------------------------------
    # ANOMALIA 1: pesagem com bruto < tara (erro de balanca/digitacao).
    # Viagem 10 (MV Vale Brasil / LogGranel): inverte valores.
    idx1 = 9  # 0-based -> id_viagem 10
    _vid, ht, tara_ok, hb, bruto_ok = pesagens_rows[idx1]
    pesagens_rows[idx1] = (_vid, ht, 16800.0, hb, 15200.0)  # liquido = -1,6 t

    # ANOMALIA 2: tempo de patio excessivo (>120 min) — caminhao retido.
    # Viagem 65 (MV Ore Amazon / EcoCargas): saida 295 min apos entrada.
    idx2 = 64
    vid2, id_atr2, cam2, transp2, ent2, sai2 = viagens_rows[idx2]
    ent_dt = datetime.strptime(ent2, "%Y-%m-%d %H:%M:%S")
    nova_saida = ent_dt + timedelta(minutes=295)
    viagens_rows[idx2] = (vid2, id_atr2, cam2, "EcoCargas", ent2, fmt(nova_saida))
    # ajusta pesagens dessa viagem para manter coerencia parcial (bruto valido,
    # mas ciclo estourado por retencao apos pesagem)
    _v, ht2, tara2, hb2, bruto2 = pesagens_rows[idx2]
    hb_dt = datetime.strptime(hb2, "%Y-%m-%d %H:%M:%S")
    if hb_dt > nova_saida:
        hb_dt = ent_dt + timedelta(minutes=90)
        pesagens_rows[idx2] = (_v, ht2, tara2, fmt(hb_dt), bruto2)

    # ANOMALIA 3: tara zerada + inversao temporal (hora_bruto < hora_tara).
    # Viagem 80 (MV Ore Amazon / TransPorto): sensor/falha de registro.
    idx3 = 79
    _v3, ht3, _t3, hb3, b3 = pesagens_rows[idx3]
    pesagens_rows[idx3] = (_v3, hb3, 0.0, ht3, b3)  # troca horarios, tara=0

    cur.executemany(
        """INSERT INTO viagens
           (id_viagem, id_atracacao, id_caminhao, transportadora, entrada_patio, saida_patio)
           VALUES (?, ?, ?, ?, ?, ?)""",
        viagens_rows,
    )
    cur.executemany(
        """INSERT INTO pesagens
           (id_viagem, hora_tara, tara_kg, hora_bruto, peso_bruto_kg)
           VALUES (?, ?, ?, ?, ?)""",
        pesagens_rows,
    )

    cur.executescript(VIEWS_SQL)
    con.commit()

    # sanity check
    n_v = cur.execute("SELECT COUNT(*) FROM viagens").fetchone()[0]
    n_p = cur.execute("SELECT COUNT(*) FROM pesagens").fetchone()[0]
    con.close()
    print(f"[seed] {db_path} criado: {n_v} viagens, {n_p} pesagens (seed={rng_seed}).")
    print("[seed] Anomalias: id_viagem 10 (bruto<tara), 65 (patio ~295min), 80 (tara=0 + inversao).")
    return db_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera porto.db (Agosto/2026).")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="Caminho do SQLite (default: ./porto.db)")
    ap.add_argument("--seed", type=int, default=42, help="Seed RNG p/ reprodutibilidade")
    args = ap.parse_args()
    seed_database(Path(args.db), rng_seed=args.seed)


if __name__ == "__main__":
    main()
