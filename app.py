from flask import Flask, request, redirect, url_for, render_template_string
import pandas as pd
import sqlite3
import os

app = Flask(__name__)
DB_PATH = "dados.db"

# ---------------- BANCO ----------------
def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS contratos (
            numero TEXT PRIMARY KEY,
            cliente TEXT,
            tipo TEXT,
            acao TEXT,
            data_encerramento TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS financeiro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_processo TEXT,
            tipo_evento TEXT,
            descricao TEXT,
            valor REAL,
            status_pagamento TEXT,
            data_prevista TEXT,
            data_recebimento TEXT
        )
        """)
init_db()

# ---------------- FUNÇÕES AUXILIARES ----------------
def pegar(row, *nomes):
    for n in nomes:
        if n in row and pd.notna(row[n]):
            return str(row[n]).strip()
    return ""

def to_float(valor):
    try:
        return float(str(valor).replace(".", "").replace(",", "."))
    except:
        return 0.0

# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():
    with db() as conn:
        contratos = conn.execute(
            "SELECT numero, cliente FROM contratos ORDER BY cliente"
        ).fetchall()

        recebido = conn.execute(
            "SELECT COALESCE(SUM(valor),0) FROM financeiro WHERE status_pagamento='RECEBIDO'"
        ).fetchone()[0]

        a_receber = conn.execute(
            "SELECT COALESCE(SUM(valor),0) FROM financeiro WHERE status_pagamento='A_RECEBER'"
        ).fetchone()[0]

        rpv = conn.execute(
            "SELECT COALESCE(SUM(valor),0) FROM financeiro WHERE tipo_evento='RPV'"
        ).fetchone()[0]

        precatorio = conn.execute(
            "SELECT COALESCE(SUM(valor),0) FROM financeiro WHERE tipo_evento='PRECATÓRIO'"
        ).fetchone()[0]

    html = """
    <h1>📊 Gestão Financeira Previdenciária</h1>

    <p><b>Total Recebido:</b> R$ {{ recebido }}</p>
    <p><b>Total a Receber:</b> R$ {{ a_receber }}</p>
    <p><b>RPV:</b> R$ {{ rpv }}</p>
    <p><b>Precatórios:</b> R$ {{ precatorio }}</p>

    <hr>

    <h3>📥 Importações</h3>

    <form action="/importar_contratos" method="POST" enctype="multipart/form-data">
        <input type="file" name="arquivo" required>
        <button type="submit">Importar Contratos (Astrea)</button>
    </form>

    <br>

    <form action="/importar_rpv" method="POST" enctype="multipart/form-data">
        <input type="file" name="arquivo" required>
        <button type="submit">Importar RPV / Financeiro</button>
    </form>

    <hr>

    <h2>Contratos</h2>
    <ul>
    {% for c in contratos %}
      <li>
        {{ c[1] }} — {{ c[0] }}
        [<a href="/financeiro/{{ c[0] }}">Financeiro</a>]
      </li>
    {% endfor %}
    </ul>
    """

    return render_template_string(
        html,
        contratos=contratos,
        recebido=f"{recebido:,.2f}",
        a_receber=f"{a_receber:,.2f}",
        rpv=f"{rpv:,.2f}",
        precatorio=f"{precatorio:,.2f}"
    )

# ---------------- IMPORTAR CONTRATOS ----------------
@app.route("/importar_contratos", methods=["POST"])
def importar_contratos():
    arquivo = request.files["arquivo"]
    df = pd.read_excel(arquivo)

    with db() as conn:
        for _, row in df.iterrows():
            numero = pegar(row, "Número", "Numero", "Processo")
            if not numero:
                continue

            conn.execute("""
            INSERT OR IGNORE INTO contratos
            (numero, cliente, tipo, acao, data_encerramento)
            VALUES (?, ?, ?, ?, ?)
            """, (
                numero,
                pegar(row, "Cliente"),
                pegar(row, "Tipo"),
                pegar(row, "Ação"),
                pegar(row, "Data de Encerramento")
            ))

    return redirect("/")

# ---------------- IMPORTAR RPV ----------------
@app.route("/importar_rpv", methods=["POST"])
def importar_rpv():
    arquivo = request.files["arquivo"]
    df = pd.read_excel(arquivo)

    print("COLUNAS RPV:", df.columns.tolist())

    inseridos = 0

    with db() as conn:
        for _, row in df.iterrows():
            numero = pegar(row, "Processo", "Número", "Numero")
            valor = to_float(pegar(row, "Honorário", "Valor a receber", "Valor"))
            status_raw = pegar(row, "Status").upper()

            conn.execute("""
            INSERT INTO financeiro (
                numero_processo,
                tipo_evento,
                descricao,
                valor,
                status_pagamento,
                data_prevista,
                data_recebimento
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                numero if numero else "SEM_PROCESSO",
                "RPV",
                f"RPV IMPORTADO | NF: {pegar(row,'Nota Fiscal')} | {pegar(row,'Observações')}",
                valor,
                "RECEBIDO" if "PAGO" in status_raw else "A_RECEBER",
                pegar(row, "Data Prevista", "Data de Expedição"),
                pegar(row, "Data Pagamento", "Data de Pagamento")
            ))

            inseridos += 1

    print(f"RPVs inseridos: {inseridos}")
    return redirect("/")

# ---------------- FINANCEIRO POR CONTRATO ----------------
@app.route("/financeiro/<numero>", methods=["GET", "POST"])
def financeiro(numero):
    with db() as conn:
        if request.method == "POST":
            conn.execute("""
            INSERT INTO financeiro (
                numero_processo, tipo_evento, descricao, valor,
                status_pagamento, data_prevista, data_recebimento
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                numero,
                request.form["tipo_evento"],
                request.form["descricao"],
                to_float(request.form["valor"]),
                request.form["status_pagamento"],
                request.form["data_prevista"],
                request.form["data_recebimento"]
            ))
            return redirect(url_for("financeiro", numero=numero))

        lancamentos = conn.execute("""
        SELECT tipo_evento, descricao, valor, status_pagamento
        FROM financeiro WHERE numero_processo=?
        """, (numero,)).fetchall()

    html = """
    <h1>💰 Financeiro — {{ numero }}</h1>

    <form method="POST">
        <label>Tipo:</label>
        <select name="tipo_evento">
            <option>HONORÁRIOS</option>
            <option>RPV</option>
            <option>PRECATÓRIO</option>
        </select><br>

        <label>Descrição:</label>
        <input name="descricao"><br>

        <label>Valor:</label>
        <input name="valor" step="0.01"><br>

        <label>Status:</label>
        <select name="status_pagamento">
            <option>RECEBIDO</option>
            <option>A_RECEBER</option>
        </select><br>

        <label>Data prevista:</label>
        <input name="data_prevista" type="date"><br>

        <label>Data recebimento:</label>
        <input name="data_recebimento" type="date"><br><br>

        <button type="submit">Salvar</button>
    </form>

    <hr>
    <h3>Lançamentos</h3>
    <ul>
    {% for l in lancamentos %}
      <li>{{ l[0] }} — {{ l[1] }} — R$ {{ l[2] }} ({{ l[3] }})</li>
    {% endfor %}
    </ul>

    <a href="/">Voltar</a>
    """

    return render_template_string(html, numero=numero, lancamentos=lancamentos)

# ---------------- START ----------------
if __name__ == "__main__":
    app.run()
