from flask import Flask, request, redirect, url_for, render_template_string
import pandas as pd
import sqlite3
import os

app = Flask(__name__)

# ---------- BANCO DE DADOS ----------
DB_PATH = "dados.db"

def conectar_db():
    return sqlite3.connect(DB_PATH)

def criar_tabelas():
    with conectar_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE,
            cliente TEXT,
            tipo TEXT,
            acao TEXT,
            data_criacao TEXT,
            data_encerramento TEXT,
            instancia_atual TEXT,
            resultado TEXT,
            url_processo TEXT,
            responsavel TEXT
        )
        """)
criar_tabelas()

# ---------- DASHBOARD ----------
@app.route("/")
def dashboard():
    with conectar_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM contratos").fetchone()[0]
        ativos = conn.execute("SELECT COUNT(*) FROM contratos WHERE data_encerramento IS NULL OR data_encerramento = ''").fetchone()[0]
        encerrados = total - ativos

    html = """
    <h1>📊 Gestão Previdenciária</h1>

    <p><b>Total de contratos:</b> {{ total }}</p>
    <p><b>Ativos:</b> {{ ativos }}</p>
    <p><b>Encerrados:</b> {{ encerrados }}</p>

    <hr>

    <h2>📥 Importar planilha do ASTREA</h2>
    <form method="POST" action="/importar" enctype="multipart/form-data">
        <input type="file" name="arquivo" accept=".xlsx" required>
        <br><br>
        <button type="submit">Importar</button>
    </form>
    """
    return render_template_string(html, total=total, ativos=ativos, encerrados=encerrados)

# ---------- IMPORTAÇÃO ASTREA ----------
@app.route("/importar", methods=["POST"])
def importar():
    arquivo = request.files["arquivo"]
    df = pd.read_excel(arquivo)

    novos = 0
    atualizados = 0

    with conectar_db() as conn:
        for _, row in df.iterrows():
            numero = str(row.get("Número", "")).strip()
            if not numero:
                continue

            existe = conn.execute(
                "SELECT id FROM contratos WHERE numero = ?",
                (numero,)
            ).fetchone()

            dados = (
                numero,
                row.get("Cliente"),
                row.get("Tipo"),
                row.get("Ação"),
                row.get("Data de Criação"),
                row.get("Data de Encerramento"),
                row.get("Instância Atual"),
                row.get("Resultado do processo"),
                row.get("URL do Processo"),
                row.get("Responsável")
            )

            if existe:
                conn.execute("""
                UPDATE contratos SET
                    cliente=?,
                    tipo=?,
                    acao=?,
                    data_criacao=?,
                    data_encerramento=?,
                    instancia_atual=?,
                    resultado=?,
                    url_processo=?,
                    responsavel=?
                WHERE numero=?
                """, dados[1:] + (numero,))
                atualizados += 1
            else:
                conn.execute("""
                INSERT INTO contratos (
                    numero, cliente, tipo, acao,
                    data_criacao, data_encerramento,
                    instancia_atual, resultado,
                    url_processo, responsavel
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, dados)
                novos += 1

    return f"""
    <h2>Importação concluída</h2>
    <p>Novos contratos: {novos}</p>
    <p>Contratos atualizados: {atualizados}</p>
    <a href="/">Voltar ao dashboard</a>
    """

if __name__ == "__main__":
    app.run()
