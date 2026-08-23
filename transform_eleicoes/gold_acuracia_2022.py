"""
Observatório Eleições 2026 — Retrovisor 2022 (gold)
===================================================
Lê os bronzes do retrovisor (Wikipedia 2022 + TSE registro 2022) e o bronze de
pesquisas 2026 já existente, e publica um único JSON com DOIS blocos:

A) `acuracia` — para cada instituto, a distância entre a ÚLTIMA pesquisa
   publicada antes de cada turno de 2022 e o resultado oficial das urnas
   (TSE). Métricas: erro médio absoluto nos 4 principais candidatos (bruto e
   sobre percentuais renormalizados — proxy de votos válidos), erro de margem
   entre os dois primeiros colocados e direção do viés (calculada, não
   editorializada). O enquadramento obrigatório (medição ≠ previsão, margem de
   erro, movimentação de véspera; NÃO é ranking de confiabilidade) vem do
   catálogo e acompanha o payload.

B) `maquina` — a máquina de medição 2022 × 2026 na MESMA altura do ciclo
   (corte espelhado por dia/mês da coleta em ambos os anos): total de
   pesquisas registradas, institutos distintos, investimento declarado
   (nominal e corrigido pelo IPCA — BACEN SGS 433, fail-soft), mediana de
   entrevistados e custo médio por pesquisa.

Uso:
    python transform_eleicoes/gold_acuracia_2022.py
Saída:
    assets/data/eleicoes_acuracia_2022.json   (consumido por fetch em runtime)
    data/gold/eleicoes_acuracia_2022.parquet  (tabela tidy instituto × turno)

Fail-soft: sem BACEN → publica só o nominal com `investimento_real_pct: null`;
sem um dos bronzes → aborta com mensagem clara (sem JSON pela metade).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from ingestion_eleicoes.catalog import (  # noqa: E402
    ACURACIA_2022_DISCLAIMER,
    ACURACIA_2022_METODOLOGIA,
    ANO_ELEICAO,
    ANO_RETROVISOR,
    DATASET_PAGE,
    DATASET_PAGE_2022,
    MAQUINA_2022_METODOLOGIA,
    QT_MIN_VALIDO,
    RESULTADO_OFICIAL_2022,
    RETROVISOR_CANDIDATOS_T1,
    RETROVISOR_CANDIDATOS_T2,
    RETROVISOR_JANELA_T1_DIAS,
    RETROVISOR_JANELA_T2_DIAS,
    RETROVISOR_T1_DATA,
    RETROVISOR_T2_DATA,
    RETROVISOR_TURNO_1,
    RETROVISOR_TURNO_2,
    WIKIPEDIA_ACURACIA_2022_URL,
)

BRONZE_RETRO = Path("data/bronze/eleicoes_acuracia_2022")
BRONZE_2026 = Path("data/bronze/eleicoes_pesquisas")
GOLD_DIR = Path("data/gold")
FRONTEND_DIR = Path("assets/data")
OUT_JSON = FRONTEND_DIR / "eleicoes_acuracia_2022.json"
OUT_PARQUET = GOLD_DIR / "eleicoes_acuracia_2022.parquet"

# BACEN SGS — IPCA, variação % no mês (mesmo padrão de gold_fundo_ipca.py;
# mesma série 433 do Brasil Cockpit). Só `requests` — sem deps novas.
SGS_IPCA_MENSAL = 433
SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
FONTE_IPCA = "Banco Central do Brasil — SGS série 433 (IPCA, variação % mensal)"
FONTE_IPCA_URL = (
    "https://www3.bcb.gov.br/sgspub/consultarvalores/telaCvsSelecionarSeries.paint"
    "?method=consultarSeries&codigoSerie=433"
)


def _latest(pattern: str, base: Path) -> Path:
    files = sorted(base.glob(pattern))
    if not files:
        raise RuntimeError(f"Sem bronze {base}/{pattern} — rode a coleta antes.")
    return files[-1]


# ─── Bloco A — acurácia ──────────────────────────────────────────────────────

def _janela(turno: str) -> tuple[str, str]:
    """(início, fim) ISO da janela de 'última medição' de cada turno: campo
    encerrado entre (eleição − N dias) e a véspera."""
    if turno == RETROVISOR_TURNO_1:
        eleicao, dias = date.fromisoformat(RETROVISOR_T1_DATA), RETROVISOR_JANELA_T1_DIAS
    else:
        eleicao, dias = date.fromisoformat(RETROVISOR_T2_DATA), RETROVISOR_JANELA_T2_DIAS
    return (eleicao - timedelta(days=dias)).isoformat(), (eleicao - timedelta(days=1)).isoformat()


def _ultima_medicao_por_instituto(wiki, turno: str):
    """DataFrame LONG da última medição de cada instituto dentro da janela."""
    ini, fim = _janela(turno)
    sub = wiki[(wiki["turno"] == turno) & wiki["dt_fim"].between(ini, fim)].copy()
    if sub.empty:
        return sub
    # última medição = maior dt_fim; desempate por maior amostra declarada.
    meta = (
        sub.groupby(["instituto", "medicao_id"])
        .agg(dt_fim=("dt_fim", "max"), amostra=("amostra", "max"))
        .reset_index()
        .sort_values(["instituto", "dt_fim", "amostra"], ascending=[True, False, False])
    )
    escolhidas = meta.groupby("instituto").head(1)["medicao_id"]
    return sub[sub["medicao_id"].isin(set(escolhidas))]


def _fmt_pp(v: float) -> str:
    return f"{abs(v):.1f}".replace(".", ",")


def _metricas_turno(wiki, turno: str) -> dict:
    """Bloco por turno: lista de institutos (ordenada por erro) + agregado."""
    import pandas as pd

    oficial = RESULTADO_OFICIAL_2022[turno]["percentuais_validos"]
    mapa = RETROVISOR_CANDIDATOS_T1 if turno == RETROVISOR_TURNO_1 else RETROVISOR_CANDIDATOS_T2
    # os dois primeiros colocados reais, para o erro de margem
    top2 = sorted(oficial, key=oficial.get, reverse=True)[:2]
    margem_real = round(oficial[top2[0]] - oficial[top2[1]], 2)

    ultimas = _ultima_medicao_por_instituto(wiki, turno)
    institutos = []
    for inst, grp in ultimas.groupby("instituto"):
        soma_listados = float(grp["pct"].sum())  # todos os candidatos testados
        pcts: dict[str, float] = {}
        pcts_validos: dict[str, float] = {}
        partidos: dict[str, str] = {}
        for _, r in grp.iterrows():
            canon = mapa.get(r["candidato"])
            if not canon or canon in pcts:
                continue
            pcts[canon] = float(r["pct"])
            partidos[canon] = str(r["partido"])
            if soma_listados > 0:
                pcts_validos[canon] = 100.0 * float(r["pct"]) / soma_listados
        if not pcts:
            continue

        erros = {c: pcts[c] - oficial[c] for c in pcts}
        erros_validos = {c: pcts_validos[c] - oficial[c] for c in pcts_validos}
        erro_medio = sum(abs(e) for e in erros.values()) / len(erros)
        erro_medio_validos = (
            sum(abs(e) for e in erros_validos.values()) / len(erros_validos)
            if erros_validos
            else None
        )
        # margem entre os dois primeiros colocados REAIS (medida − real):
        # negativo = mediu margem menor (ou invertida) para o vencedor real.
        erro_margem = margem_medida = None
        if top2[0] in pcts and top2[1] in pcts:
            margem_medida = round(pcts[top2[0]] - pcts[top2[1]], 2)
            erro_margem = round(margem_medida - margem_real, 2)
        # direção do viés: maior erro absoluto entre os candidatos avaliados
        c_vies = max(erros, key=lambda c: abs(erros[c]))
        verbo = "subestimou" if erros[c_vies] < 0 else "superestimou"
        direcao = f"{verbo} {c_vies} em {_fmt_pp(erros[c_vies])} pp"

        r0 = grp.iloc[0]
        institutos.append(
            {
                "instituto": inst,
                "contratante": r0["contratante"] if pd.notna(r0["contratante"]) else None,
                "data_pesquisa": str(grp["dt_fim"].max()),
                "amostra": int(r0["amostra"]) if pd.notna(r0["amostra"]) else None,
                "margem_erro_pp": float(r0["margem_pp"]) if pd.notna(r0["margem_pp"]) else None,
                "candidatos": [
                    {
                        "nome": c,
                        "partido": partidos[c],
                        "pct_pesquisa": round(pcts[c], 2),
                        "pct_pesquisa_validos": (
                            round(pcts_validos[c], 2) if c in pcts_validos else None
                        ),
                        "pct_urna": oficial[c],
                        "erro_pp": round(erros[c], 2),
                        "erro_validos_pp": (
                            round(erros_validos[c], 2) if c in erros_validos else None
                        ),
                    }
                    for c in sorted(pcts, key=oficial.get, reverse=True)
                ],
                "n_candidatos_avaliados": len(pcts),
                "soma_candidatos_pct": round(soma_listados, 1),
                "erro_medio_abs_pp": round(erro_medio, 2),
                "erro_medio_abs_validos_pp": (
                    round(erro_medio_validos, 2) if erro_medio_validos is not None else None
                ),
                "margem_medida_pp": margem_medida,
                "margem_real_pp": margem_real,
                "erro_margem_pp": erro_margem,
                "direcao_vies": direcao,
            }
        )

    # apresentação natural: menor → maior erro (o texto carrega o enquadramento)
    institutos.sort(key=lambda i: i["erro_medio_abs_pp"])

    def _mediana(vals: list[float]) -> float | None:
        vals = sorted(vals)
        if not vals:
            return None
        n = len(vals)
        m = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        return round(m, 2)

    ini, fim = _janela(turno)
    return {
        "janela": {
            "regra": (
                f"última pesquisa de cada instituto com campo encerrado nos "
                f"{RETROVISOR_JANELA_T1_DIAS if turno == RETROVISOR_TURNO_1 else RETROVISOR_JANELA_T2_DIAS} "
                f"dias anteriores à eleição (véspera inclusa; dia da urna excluso)"
            ),
            "inicio": ini,
            "fim": fim,
        },
        "cenario": "estimulado" if turno == RETROVISOR_TURNO_1 else "confronto final",
        "institutos": institutos,
        "agregado": {
            "n_institutos": len(institutos),
            "mediana_erro_medio_abs_pp": _mediana([i["erro_medio_abs_pp"] for i in institutos]),
            "mediana_erro_medio_abs_validos_pp": _mediana(
                [i["erro_medio_abs_validos_pp"] for i in institutos if i["erro_medio_abs_validos_pp"] is not None]
            ),
            "mediana_erro_margem_abs_pp": _mediana(
                [abs(i["erro_margem_pp"]) for i in institutos if i["erro_margem_pp"] is not None]
            ),
        },
    }


# ─── Bloco B — máquina 2022 × 2026 ───────────────────────────────────────────

def _limpar_tse(df):
    """Mesmas regras de qualidade do gold de 2026 (gold_eleicoes._limpar)."""
    import pandas as pd

    df = df.copy()
    df["qt_entrevistado"] = pd.to_numeric(
        df["qt_entrevistado"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    df["vr_pesquisa"] = pd.to_numeric(
        df["vr_pesquisa"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    df["dt_divulgacao"] = pd.to_datetime(df["dt_divulgacao"], errors="coerce")
    df.loc[df["qt_entrevistado"] < QT_MIN_VALIDO, "qt_entrevistado"] = pd.NA
    df.loc[df["vr_pesquisa"] < 0, "vr_pesquisa"] = pd.NA
    return df


def _metricas_maquina(df, corte) -> dict:
    import pandas as pd

    sub = df[df["dt_divulgacao"] <= pd.Timestamp(corte)]
    q = sub["qt_entrevistado"].dropna()
    custos = sub["vr_pesquisa"].dropna()
    custos = custos[custos > 0]
    mediana = q.median()
    return {
        "total_pesquisas": int(len(sub)),
        "institutos": int(sub["empresa"].nunique()),
        "investimento_nominal_rs": round(float(sub["vr_pesquisa"].fillna(0).sum()), 2),
        "mediana_entrevistados": int(mediana) if pd.notna(mediana) else None,
        "custo_medio_rs": round(float(custos.mean()), 2) if len(custos) else None,
    }


def _fetch_fator_ipca(corte_2022: date) -> dict | None:
    """Fator IPCA acumulado do mês seguinte ao corte de 2022 até o último mês
    publicado. None em qualquer falha (fail-soft — publica só o nominal)."""
    ini_ano, ini_mes = (corte_2022.year + (1 if corte_2022.month == 12 else 0),
                        1 if corte_2022.month == 12 else corte_2022.month + 1)
    try:
        resp = requests.get(
            SGS_URL.format(code=SGS_IPCA_MENSAL),
            params={
                "formato": "json",
                "dataInicial": f"01/{ini_mes:02d}/{ini_ano}",
                "dataFinal": date.today().strftime("%d/%m/%Y"),
            },
            timeout=30,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        serie = resp.json()
    except Exception as e:  # noqa: BLE001 — fail-soft
        print(f"  ✗ BACEN SGS indisponível ({e}) — publicando só o nominal.")
        return None
    if not serie:
        return None
    fator = 1.0
    for pt in serie:
        try:
            fator *= 1 + float(pt["valor"]) / 100.0
        except (KeyError, ValueError, TypeError):
            continue
    ref = serie[-1]["data"]  # 'DD/MM/YYYY'
    return {
        "indice": "IPCA",
        "serie_sgs": SGS_IPCA_MENSAL,
        "base": f"reais de {corte_2022.month:02d}/{corte_2022.year} (mês do corte)",
        "ref_mes": f"{ref.split('/')[2]}-{ref.split('/')[1]}",
        "fator": round(fator, 4),
        "acumulado_pct": round((fator - 1) * 100, 1),
        "fonte": FONTE_IPCA,
        "fonte_url": FONTE_IPCA_URL,
    }


def _pct(a: float | int | None, b: float | int | None) -> float | None:
    if not a or b is None:
        return None
    return round(100.0 * (b - a) / a, 1)


# ─── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    import pandas as pd

    print("🗳  Observatório Eleições 2026 — Retrovisor 2022 (gold)")

    src_wiki = _latest("wiki_2022_*.parquet", BRONZE_RETRO)
    src_tse22 = _latest("tse_pesquisas_2022_*.parquet", BRONZE_RETRO)
    src_tse26 = _latest("pesquisas_*.parquet", BRONZE_2026)
    wiki = pd.read_parquet(src_wiki)
    tse22 = _limpar_tse(pd.read_parquet(src_tse22))
    tse26 = _limpar_tse(pd.read_parquet(src_tse26))
    print(f"  • bronze wiki 2022: {src_wiki.name} ({len(wiki):,} linhas)")
    print(f"  • bronze TSE 2022:  {src_tse22.name} ({len(tse22):,} registros)")
    print(f"  • bronze TSE 2026:  {src_tse26.name} ({len(tse26):,} registros)")

    # ── A) acurácia por turno ──
    acuracia = {
        "resultado_oficial": RESULTADO_OFICIAL_2022,
        "turno1": _metricas_turno(wiki, RETROVISOR_TURNO_1),
        "turno2": _metricas_turno(wiki, RETROVISOR_TURNO_2),
        "notas": {
            "base_percentual": (
                "pct_pesquisa = % sobre o total de entrevistados (como publicado); "
                "pct_pesquisa_validos = renormalizado entre os candidatos testados "
                "na mesma pesquisa (proxy de votos válidos); pct_urna = % oficial "
                "de votos válidos (TSE)."
            ),
            "erro_margem": (
                "margem entre os dois primeiros colocados reais (medida − real); "
                "negativo = a pesquisa mediu margem menor (ou invertida) para o "
                "vencedor real."
            ),
            "ordenacao": "institutos ordenados do menor para o maior erro médio absoluto.",
        },
    }

    # ── B) máquina 2022 × 2026, corte espelhado ──
    # Âncora do espelho: a data do SNAPSHOT do bronze de 2026 (nome do arquivo),
    # não a data de execução — o conhecimento do lado 2026 termina no snapshot,
    # então espelhar o dia/mês dele em 2022 é o corte mais justo (e o corte
    # acompanha sozinho quando o CI recoletar o bronze). Fallback: data UTC.
    import re

    m = re.match(r"pesquisas_(\d{4})_(\d{2})_(\d{2})\.parquet$", src_tse26.name)
    if m:
        snap = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        snap = datetime.now(timezone.utc).date()
    try:
        corte_2022 = date(ANO_RETROVISOR, snap.month, snap.day)
        corte_2026 = date(ANO_ELEICAO, snap.month, snap.day)
    except ValueError:  # 29/02 fora de ano bissexto
        corte_2022 = date(ANO_RETROVISOR, snap.month, snap.day - 1)
        corte_2026 = date(ANO_ELEICAO, snap.month, snap.day - 1)

    m22 = _metricas_maquina(tse22, corte_2022)
    m26 = _metricas_maquina(tse26, corte_2026)

    ipca = _fetch_fator_ipca(corte_2022)
    invest_corrigido = None
    invest_real_pct = None
    if ipca:
        invest_corrigido = round(m22["investimento_nominal_rs"] * ipca["fator"], 2)
        invest_real_pct = _pct(invest_corrigido, m26["investimento_nominal_rs"])
    m22["investimento_corrigido_ipca_rs"] = invest_corrigido

    maquina = {
        "corte": {
            "regra": (
                "registros com data de divulgação até o mesmo dia/mês em cada ano "
                "(mesma altura do ciclo, espelhada na data do snapshot de 2026)"
            ),
            "a2022": corte_2022.isoformat(),
            "a2026": corte_2026.isoformat(),
        },
        "a2022": m22,
        "a2026": m26,
        "variacao": {
            "pesquisas_pct": _pct(m22["total_pesquisas"], m26["total_pesquisas"]),
            "institutos_pct": _pct(m22["institutos"], m26["institutos"]),
            "investimento_nominal_pct": _pct(
                m22["investimento_nominal_rs"], m26["investimento_nominal_rs"]
            ),
            "investimento_real_pct": invest_real_pct,
        },
        "ipca": ipca if ipca else {"indisponivel": True},
    }

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fontes": [
            {
                "label": "Wikipedia PT — Pesquisas de opinião para a eleição presidencial no Brasil em 2022 (agrega pesquisas registradas no TSE)",
                "url": WIKIPEDIA_ACURACIA_2022_URL,
            },
            {"label": "TSE — Portal de Dados Abertos, Pesquisas Eleitorais 2022", "url": DATASET_PAGE_2022},
            {"label": "TSE — Portal de Dados Abertos, Pesquisas Eleitorais 2026", "url": DATASET_PAGE},
            {
                "label": RESULTADO_OFICIAL_2022["turno1"]["fonte"],
                "url": RESULTADO_OFICIAL_2022["turno1"]["fonte_url"],
            },
            {
                "label": RESULTADO_OFICIAL_2022["turno2"]["fonte"],
                "url": RESULTADO_OFICIAL_2022["turno2"]["fonte_url"],
            },
            {"label": FONTE_IPCA, "url": FONTE_IPCA_URL},
        ],
        "metodologia": {
            "acuracia": ACURACIA_2022_METODOLOGIA,
            "maquina": MAQUINA_2022_METODOLOGIA,
        },
        "disclaimer": ACURACIA_2022_DISCLAIMER,
        "acuracia": acuracia,
        "maquina": maquina,
    }

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    # gold parquet: tabela tidy instituto × turno (reuso analítico)
    tidy = []
    for turno in (RETROVISOR_TURNO_1, RETROVISOR_TURNO_2):
        for i in acuracia[turno]["institutos"]:
            tidy.append(
                {
                    "turno": turno,
                    "instituto": i["instituto"],
                    "contratante": i["contratante"],
                    "data_pesquisa": i["data_pesquisa"],
                    "amostra": i["amostra"],
                    "margem_erro_pp": i["margem_erro_pp"],
                    "erro_medio_abs_pp": i["erro_medio_abs_pp"],
                    "erro_medio_abs_validos_pp": i["erro_medio_abs_validos_pp"],
                    "erro_margem_pp": i["erro_margem_pp"],
                    "direcao_vies": i["direcao_vies"],
                }
            )
    pd.DataFrame(tidy).to_parquet(OUT_PARQUET, index=False)

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ag1 = acuracia["turno1"]["agregado"]
    ag2 = acuracia["turno2"]["agregado"]
    print(f"  ✓ {OUT_JSON}")
    print(
        f"    acurácia 1º turno: {ag1['n_institutos']} institutos · mediana do erro "
        f"{ag1['mediana_erro_medio_abs_pp']} pp (válidos {ag1['mediana_erro_medio_abs_validos_pp']} pp)"
    )
    print(
        f"    acurácia 2º turno: {ag2['n_institutos']} institutos · mediana do erro "
        f"{ag2['mediana_erro_medio_abs_pp']} pp (válidos {ag2['mediana_erro_medio_abs_validos_pp']} pp)"
    )
    print(
        f"    máquina  {ANO_RETROVISOR}: {m22['total_pesquisas']:,} pesquisas · {m22['institutos']} institutos · "
        f"R$ {m22['investimento_nominal_rs']:,.0f}"
    )
    print(
        f"    máquina  {ANO_ELEICAO}: {m26['total_pesquisas']:,} pesquisas · {m26['institutos']} institutos · "
        f"R$ {m26['investimento_nominal_rs']:,.0f}"
    )
    v = maquina["variacao"]
    real_txt = f"{v['investimento_real_pct']:+}%" if v["investimento_real_pct"] is not None else "n/d"
    print(
        f"    variação: pesquisas {v['pesquisas_pct']:+}% · institutos {v['institutos_pct']:+}% · "
        f"investimento nominal {v['investimento_nominal_pct']:+}% · real {real_txt}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
