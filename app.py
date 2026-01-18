from flask import Flask, request, redirect, url_for, render_template_string
import pandas as pd
import sqlite3
from datetime import datetime

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
            status TEXT DEFAULT 'ATIVO',
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
            data_evento TEXT
        )
        """)
init_db()

# ---------------- UTIL ----------------
def to_float(v):
    try:
        return float(str(v).replace(".", "").replace(",", "."))
    except:
        return 0.0

def ano(data):
    try:
        return datetime.strptime(data, "%Y-%m-%d").year
    except:
        return None

def mes(data):
    try:
        return datetime.strptime(data, "%Y-%m-%d").strftime("%Y-%m")
    except:
        return None

# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():
    with db() as conn:
        total_contratos = conn.execute("SELECT COUNT(*) FROM contratos").fetchone()[0]
        ativos = conn.execute("SELECT COUNT(*) FROM contratos WHERE status='ATIVO'").fetchone()[0]
        encerrados = conn.execute("SELECT COUNT(*) FROM contratos WHERE status='ENCERRADO'").fetchone()[0]

        total_faturado = conn.execute(
            "SELECT COALESCE(SUM(valor),0) FROM financeiro"
        ).fetchone()[0]

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

        honorarios = conn.execute(
            "SELECT COALESCE(SUM(valor),0) FROM financeiro WHERE tipo_evento='HONORÁRIOS'"
        ).fetchone()[0]

        faturado_por_ano = conn.execute("""
            SELECT substr(data_evento,1,4) as ano, SUM(valor)
            FROM financeiro
            GROUP BY ano
            ORDER BY ano
        """).fetchall()

        recebido_por_mes = conn.execute("""
            SELECT substr(data_evento,1,7) as mes, SUM(valor)
            FROM financeiro
            WHERE status_pagamento='RECEBIDO'
            GROUP BY mes
            ORDER BY mes
        """).fetchall()

        contratos = conn.execute(
            "SELECT numero, cliente FROM contratos ORDER BY cliente"
        ).fetchall()

    html = """
    <h1>📊 Gestão Financeira Previdenciária</h1>

    <h2>Contratos</h2>
    <ul>
        <li>Total: {{ total_contratos }}</li>
        <li>Ativos: {{ ativos }}</li>
        <li>Encerrados: {{ encerrados }}</li>
    </ul>

    <h2>Financeiro Geral</h2>
    <ul>
        <li>Total Faturado: R$ {{ total_faturado }}</li>
        <li>Total Recebido: R$ {{ recebido }}</li>
        <li>Total a Receber: R$ {{ a_receber }}</li>
        <li>Honorários: R$ {{ honorarios }}</li>
        <li>RPV: R$ {{ rpv }}</li>
        <li>Precatório: R$ {{ precatorio }}</li>
    </ul>

    <h3>Faturamento por Ano</h3>
    <ul>
    {% for a in faturado_por_ano %}
        <li>{{ a[0] }}: R$ {{ a[1] }}</li>
    {% endfor %}
    </ul>

    <h3>Recebido por Mês</h3>
    <ul>
    {% for m in recebido_por_mes %}
        <li>{{ m[0] }}: R$ {{ m[1] }}</li>
    {% endfor %}
    </ul>

    <hr>

    <h3>📥 Importar Contratos (Astrea)</h3>
    <form action="/importar_contratos" method="POST" enctype="multipart/form-data">
        <input type="file" name="arquivo" required>
        <button type="submit">Importar</button>
    </form>

    <hr>

    <h3>Contratos</h3>
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
        total_contratos=total_contratos,
        ativos=ativos,
        encerrados=encerrados,
        total_faturado=f"{total_faturado:,.2f}",
        recebido=f"{recebido:,.2f}",
        a_receber=f"{a_receber:,.2f}",
        honorarios=f"{honorarios:,.2f}",
        rpv=f"{rpv:,.2f}",
        precatorio=f"{precatorio:,.2f}",
        faturado_por_ano=faturado_por_ano,
        recebido_por_mes=recebido_por_mes,
        contratos=contratos
    )

# ---------------- IMPORTAR CONTRATOS ----------------
@app.route("/importar_contratos", methods=["POST"])
def importar_contratos():
    arquivo = request.files["arquivo"]
    df = pd.read_excel(arquivo)

    with db() as conn:
        for _, row in df.iterrows():
            numero = str(row.get("Número", "")).strip()
            if not numero:
                continue
            conn.execute("""
            INSERT OR IGNORE INTO contratos
            (numero, cliente)
            VALUES (?, ?)
            """, (
                numero,
                row.get("Cliente", "")
            ))
    return redirect("/")

# ---------------- FINANCEIRO POR CONTRATO ----------------
@app.route("/financeiro/<numero>", methods=["GET", "POST"])
def financeiro(numero):
    with db() as conn:
        if request.method == "POST":
            conn.execute("""
            INSERT INTO financeiro
            (numero_processo, tipo_evento, descricao, valor, status_pagamento, data_evento)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                numero,
                request.form["tipo_evento"],
                request.form["descricao"],
                to_float(request.form["valor"]),
                request.form["status_pagamento"],
                request.form["data_evento"]
            ))
            return redirect(url_for("financeiro", numero=numero))

        lancamentos = conn.execute("""
        SELECT tipo_evento, descricao, valor, status_pagamento, data_evento
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
        <input name="valor"><br>

        <label>Status:</label>
        <select name="status_pagamento">
            <option>RECEBIDO</option>
            <option>A_RECEBER</option>
        </select><br>

        <label>Data:</label>
        <input name="data_evento" type="date"><br><br>

        <button type="submit">Salvar</button>
    </form>

    <hr>
    <h3>Lançamentos</h3>
    <ul>
    {% for l in lancamentos %}
      <li>{{ l[4] }} — {{ l[0] }} — {{ l[1] }} — R$ {{ l[2] }} ({{ l[3] }})</li>
    {% endfor %}
    </ul>

    <a href="/">Voltar</a>
    """

    return render_template_string(html, numero=numero, lancamentos=lancamentos)

# ---------------- START ----------------
if __name__ == "__main__":
    app.run()
