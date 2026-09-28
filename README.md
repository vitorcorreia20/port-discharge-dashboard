# Port Discharge Dashboard — Granel Sólido (Agosto/2026)

Dashboard executivo em **Python + Streamlit + Plotly + SQLite** para a descarga
navio → caminhão: entrada vazio → pesagem tara → carregamento no cais →
pesagem bruto → saída do pátio.

Arquivos:

| Arquivo | Papel |
|---|---|
| `seed_data.py` | Cria `porto.db`, tabelas, dados fictícios de Ago/2026 e as 3 views |
| `app.py` | Dashboard Streamlit (KPIs, curva S, pátio por transportadora, auditoria) |
| `porto.db` | Banco SQLite gerado (não versionar se preferir; regenere com o seed) |
| `relatorio_executivo.md` | Análise de 1 página para o Gerente de Operações |
| `requirements.txt` | Dependências |

## 1. Passo a passo (Windows PowerShell)

```powershell
# 1) Entrar na pasta do projeto
Set-Location "C:\Users\tmend\Projetos\port-discharge-dashboard"

# 2) Criar e ativar o virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Instalar dependências
pip install -r requirements.txt

# 4) Gerar o banco (opcional — o app gera sozinho se faltar)
python seed_data.py

# 5) Rodar o dashboard
streamlit run app.py
```

Abra o endereço exibido no terminal (geralmente http://localhost:8501).
Filtros na barra lateral: **Navio/Atracação** e **Transportadora**.

> Regenerar do zero: apague `porto.db` e rode `python seed_data.py`
> (ou só abra o app — ele detecta a ausência e semeia automaticamente).
> Reprodutibilidade: `python seed_data.py --seed 42 --db porto.db`.

## 2. Sustentação / handoff — como conectar novos dados

**Onde ficam os dados:** tudo no SQLite `porto.db`, tabelas `atracacoes`,
`viagens`, `pesagens` (chaves: `viagens.id_atracacao → atracacoes`,
`pesagens.id_viagem → viagens`).

**Carga incremental (novo navio / novas viagens):** datas em texto ISO
`YYYY-MM-DD HH:MM:SS`. Exemplo:

```sql
INSERT INTO atracacoes
  (id_atracacao, navio, carga, toneladas_manifestadas,
   atracacao, inicio_descarga, fim_descarga, desatracacao)
VALUES
  (3, 'MV Ore Pantanal', 'Minerio de Ferro', 4200.0,
   '2026-08-22 07:00:00', '2026-08-22 13:00:00', NULL, NULL);

INSERT INTO viagens
  (id_atracacao, id_caminhao, transportadora, entrada_patio, saida_patio)
VALUES
  (3, 'ABC-1234', 'TransPorto', '2026-08-22 13:05:00', '2026-08-22 14:02:00');

-- use o id_viagem gerado (last_insert_rowid) na pesagem:
INSERT INTO pesagens
  (id_viagem, hora_tara, tara_kg, hora_bruto, peso_bruto_kg)
VALUES
  (last_insert_rowid(), '2026-08-22 13:12:00', 15200, '2026-08-22 13:55:00', 46300);
```

Regras de consistência (as mesmas da auditoria do app): exigir
`peso_bruto_kg > tara_kg`, `tara_kg > 0`, `hora_bruto >= hora_tara`,
`saida_patio >= entrada_patio`, ciclo de pátio ≤ 120 min. Para navio em
operação deixe `fim_descarga`/`desatracacao = NULL`; ao concluir, preencha —
as views passam a usar o fim real automaticamente.

**Atualizar as views:** elas já estão no banco. Para recriar após ajuste,
rode o `CREATE VIEW` correspondente (definições em `seed_data.py`,
constante `VIEWS_SQL`) ou regenere tudo com `python seed_data.py`
(atenção: o seed **apaga e recria** o banco — para produção, aplique
`INSERT`s em vez de ressemear).

**Validação rápida após carga:**

```sql
SELECT * FROM vw_kpi_prancha;
SELECT * FROM vw_kpi_progresso;
SELECT * FROM vw_kpi_tempo_ciclo;
SELECT v.id_viagem FROM viagens v JOIN pesagens p ON p.id_viagem = v.id_viagem
WHERE p.peso_bruto_kg <= p.tara_kg OR p.tara_kg <= 0;  -- esperado: 0 linhas
```

## 3. Dicionário de dados

**`atracacoes`**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_atracacao` | INTEGER PK | Identificador da atracação |
| `navio` | TEXT | Nome do navio (ex: MV Vale Brasil) |
| `carga` | TEXT | Tipo de granéis (ex: Minério de Ferro) |
| `toneladas_manifestadas` | REAL | Meta do manifesto (t) |
| `atracacao` | TEXT | Data/hora da atracação (ISO) |
| `inicio_descarga` | TEXT | Início da descarga (ISO) |
| `fim_descarga` | TEXT NULL | Fim da descarga; NULL = em operação |
| `desatracacao` | TEXT NULL | Desatracação; NULL = ainda atracado |

**`viagens`**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_viagem` | INTEGER PK | Identificador da viagem (caminhão carregado) |
| `id_atracacao` | INTEGER FK | Navio de origem |
| `id_caminhao` | TEXT | Placa fictícia |
| `transportadora` | TEXT | TransPorto / LogGranel / EcoCargas |
| `entrada_patio` | TEXT | Entrada do vazio no pátio (ISO) |
| `saida_patio` | TEXT | Saída carregado do pátio (ISO) |

**`pesagens`**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_pesagem` | INTEGER PK | Identificador da pesagem |
| `id_viagem` | INTEGER FK | Viagem correspondente (1:1) |
| `hora_tara` | TEXT | Pesagem do caminhão vazio (ISO) |
| `tara_kg` | REAL | Tara em kg |
| `hora_bruto` | TEXT | Pesagem do caminhão carregado (ISO) |
| `peso_bruto_kg` | REAL | Peso bruto em kg |

## 4. Métricas calculadas

| Métrica | Fórmula (SQLite) | Onde |
|---|---|---|
| Peso líquido (t) | `(peso_bruto_kg - tara_kg) / 1000.0` | app + views |
| Prancha média (t/h) | `SUM(líquido) / ((JULIANDAY(fim) - JULIANDAY(início)) * 24)`; se `fim_descarga IS NULL`, usa `MAX(hora_bruto)` como fim provisório | `vw_kpi_prancha` |
| Progresso (%) | `SUM(líquido) / toneladas_manifestadas * 100` | `vw_kpi_progresso` |
| Tempo de pátio (min) | `(JULIANDAY(saida_patio) - JULIANDAY(entrada_patio)) * 1440`, com `AVG/MIN/MAX` por transportadora | `vw_kpi_tempo_ciclo` |
| Auditoria | `bruto ≤ tara` · `tara ≤ 0` · `hora_bruto < hora_tara` · ciclo `> 120 min` | tabela do `app.py` |

KPIs e curva S consideram **apenas pesagens válidas**; inconsistências
permanecem nas tabelas base e aparecem destacadas na auditoria.

## 5. Dados fictícios incluídos

- **MV Vale Brasil** (concluído 04–10/08, 1.650 t manifestadas, 48 viagens) e
  **MV Ore Amazon** (em operação desde 14/08, 3.800 t, 42 viagens).
- ~31 t/viagem; perfis de pátio distintos por transportadora
  (TransPorto enxuta, EcoCargas gargalo).
- **3 anomalias intencionais:** viagem 10 (bruto < tara), 65 (pátio ~295 min),
  80 (tara zerada + inversão temporal).
