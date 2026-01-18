from flask import Flask, render_template_string

app = Flask(__name__)

@app.route("/")
def dashboard():
    html = """
    <h1>📊 Gestão Financeira Previdenciária</h1>

    <p><b>Status:</b> Sistema online funcionando corretamente.</p>

    <h2>Contratos</h2>
    <ul>
        <li>Ativos: 0</li>
        <li>Encerrados: 0</li>
    </ul>

    <h2>Financeiro</h2>
    <ul>
        <li>Total Recebido: R$ 0,00</li>
        <li>Total a Receber: R$ 0,00</li>
        <li>RPV: R$ 0,00</li>
        <li>Precatórios: R$ 0,00</li>
    </ul>

    <p style="margin-top:30px;color:green;">
        ✔ Base pronta para integração com ASTREA
    </p>
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run()
