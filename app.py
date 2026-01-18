from flask import Flask, request, redirect, url_for, render_template_string
import pandas as pd
import sqlite3

app = Flask(__name__)
DB_PATH = "dados.db"

# ---------- BANCO DE DADOS ----------
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

# ---------- DASHBOARD ----------
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

    <h2>📥 Importar planilha do ASTREA</h2>
    <form action="/importar" method="POST" enctype="multipart/form-data">
        <input type="file" name="arquivo" accept=".xlsx" required>
        <button type="submit">Importar</button>
    </form>

    <hr>

    <h2>Contratos</h2>
    <ul>
    {% for c in contratos %}
        <li>
            {{ c[1] }} — {{ c[0] }}
            [ <a href="/financeiro/{{ c[0] }}">Financeiro</a> ]
        </li>
    {% else %}
        <li><i>Nenhum contrato importado ainda</i></li>
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

# ---------- IMPORTAÇÃO ASTREA ----------
@app.route("/importar", methods=["POST"])
def importar():
    arquivo = request.files["arquivo"]
    df = pd.read_excel(arquivo)

    with db() as conn:
        for _, row in df.iterrows():
            numero = str(row.get("Número", "")).strip()
            if not numero:
                continue

            conn.execute("""
            INSERT OR IGNORE INTO contratos
            (numero, cliente, tipo, acao, data_encerramento)
            VALUES (?, ?, ?, ?, ?)
            """, (
                numero,
                row.get("Cliente", ""),
                row.get("Tipo", ""),
                row.get("Ação", ""),
                row.get("Data de Encerramento", "")
            ))

    return redirect("/")

# ---------- FINANCEIRO POR CONTRATO ----------
@app.route("/financeiro/<numero>", methods=["GET", "POST"])
def financeiro(numero):
    with db() as conn:
        if request.method == "POST":
            conn.execute("""
            INSERT INTO financeiro
            (numero_processo, tipo_evento, descricao, valor,
             status_pagamento, data_prevista, data_recebimento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                numero,
                request.form["tipo_evento"],
                request.form["descricao"],
                float(request.form["valor"]),
                request.form["status_pagamento"],
                request.form["data_prevista"],
                request.form["data_recebimento"]
            ))
            return redirect(url_for("financeiro", numero=numero))

        lancamentos = conn.execute("""
        SELECT tipo_evento, descricao, valor, status_pagamento
        FROM financeiro
        WHERE numero_processo=?
        """, (numero,)).fetchall()

    html = """
    <h1>💰 Financeiro — Processo {{ numero }}</h1>

    <form method="POST">
        <label>Tipo:</label>
        <select name="tipo_evento">
            <option>HONORÁRIOS</option>
            <option>RPV</option>
            <option>PRECATÓRIO</option>
        </select><br><br>

        <label>Descrição:</label><br>
        <input name="descricao" required><br><br>

        <label>Valor:</label><br>
        <input name="valor" type="number" step="0.01" required><br><br>

        <label>Status:</label>
        <select name="status_pagamento">
            <option>RECEBIDO</option>
            <option>A_RECEBER</option>
        </select><br><br>

        <label>Data prevista:</label>
        <input name="data_prevista" type="date"><br><br>

        <label>Data recebimento:</label>
        <input name="data_recebimento" type="date"><br><br>

        <button type="submit">Salvar lançamento</button>
    </form>

    <hr>

    <h3>Lançamentos</h3>
    <ul>
    {% for l in lancamentos %}
        <li>{{ l[0] }} — {{ l[1] }} — R$ {{ l[2] }} ({{ l[3] }})</li>
    {% else %}
        <li><i>Nenhum lançamento ainda</i></li>
    {% endfor %}
    </ul>

    <a href="/">⬅ Voltar ao dashboard</a>
    """
    return render_template_string(html, numero=numero, lancamentos=lancamentos)

if __name__ == "__main__":
    app.run()
