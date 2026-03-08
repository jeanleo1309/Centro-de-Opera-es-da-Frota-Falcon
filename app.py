from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta, date

app = Flask(__name__)


# conexão com banco
def conectar():
    return sqlite3.connect("database.db")


# criar banco
def init_db():

    conn = conectar()
    c = conn.cursor()

    # tabela helicópteros
    c.execute("""
    CREATE TABLE IF NOT EXISTS helicopteros(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prefixo TEXT UNIQUE,
        consumo REAL,
        combustivel REAL
    )
    """)

    # tabela voos
    c.execute("""
    CREATE TABLE IF NOT EXISTS voos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        helicoptero_id INTEGER,
        data TEXT,
        hora TEXT,
        duracao REAL,
        combustivel_usado REAL,
        status TEXT
    )
    """)

    frota = [
        "AMM","RVP","GBC","JCM","RGT",
        "VVF","HOJ","HPA","HPH","YDG"
    ]

    for heli in frota:

        c.execute("""
        INSERT OR IGNORE INTO helicopteros(prefixo,consumo,combustivel)
        VALUES(?,?,?)
        """,(heli,60,0))

    conn.commit()
    conn.close()


init_db()


# -------------------------
# cálculo tempo restante
# -------------------------

def tempo_restante(hora_voo):

    agora = datetime.now()

    try:
        voo = datetime.strptime(hora_voo, "%H:%M")
        voo = voo.replace(
            year=agora.year,
            month=agora.month,
            day=agora.day
        )
    except:
        return 0

    diferenca = voo - agora

    minutos = int(diferenca.total_seconds() / 60)

    return minutos


# -------------------------
# página principal
# -------------------------

@app.route("/")
def index():

    conn = conectar()
    c = conn.cursor()

    helicopteros = c.execute(
        "SELECT * FROM helicopteros"
    ).fetchall()

    voos = c.execute("""
    SELECT voos.id,
           helicopteros.prefixo,
           voos.data,
           voos.hora,
           voos.duracao,
           voos.status
    FROM voos
    JOIN helicopteros
    ON voos.helicoptero_id = helicopteros.id
    ORDER BY voos.data, voos.hora
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        helicopteros=helicopteros,
        voos=voos
    )


# -------------------------
# agendar voo
# -------------------------

@app.route("/agendar_voo", methods=["POST"])
def agendar_voo():

    heli = request.form["heli"]
    data = request.form["data"]
    hora = request.form["hora"]
    duracao = float(request.form["duracao"])

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO voos(helicoptero_id,data,hora,duracao,status)
    VALUES(?,?,?,?,?)
    """,(heli,data,hora,duracao,"agendado"))

    conn.commit()
    conn.close()

    return redirect("/")


# -------------------------
# confirmar voo
# -------------------------

@app.route("/confirmar_voo", methods=["POST"])
def confirmar_voo():

    voo_id = request.form["voo_id"]

    conn = conectar()
    c = conn.cursor()

    voo = c.execute("""
    SELECT helicoptero_id,duracao
    FROM voos
    WHERE id=?
    """,(voo_id,)).fetchone()

    heli_id = voo[0]
    duracao = voo[1]

    heli = c.execute("""
    SELECT consumo,combustivel
    FROM helicopteros
    WHERE id=?
    """,(heli_id,)).fetchone()

    consumo = heli[0]

    combustivel_usado = (duracao / 60) * consumo

    c.execute("""
    UPDATE helicopteros
    SET combustivel = combustivel - ?
    WHERE id=?
    """,(combustivel_usado,heli_id))

    c.execute("""
    UPDATE voos
    SET status='realizado',
        combustivel_usado=?
    WHERE id=?
    """,(combustivel_usado,voo_id))

    conn.commit()
    conn.close()

    return redirect("/")


# -------------------------
# abastecer
# -------------------------

@app.route("/abastecer", methods=["POST"])
def abastecer():

    heli_id = request.form["id"]
    litros = float(request.form["litros"])

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    UPDATE helicopteros
    SET combustivel = combustivel + ?
    WHERE id=?
    """,(litros,heli_id))

    conn.commit()
    conn.close()

    return redirect("/")


# -------------------------
# registrar voo manual
# -------------------------

@app.route("/voo", methods=["POST"])
def voo():

    heli_id = request.form["id"]
    duracao = float(request.form["duracao"])

    conn = conectar()
    c = conn.cursor()

    heli = c.execute("""
    SELECT consumo, combustivel
    FROM helicopteros
    WHERE id=?
    """,(heli_id,)).fetchone()

    consumo = heli[0]

    combustivel_usado = (duracao/60) * consumo

    c.execute("""
    UPDATE helicopteros
    SET combustivel = combustivel - ?
    WHERE id=?
    """,(combustivel_usado,heli_id))

    conn.commit()
    conn.close()

    return redirect("/")


# -------------------------
# radar operacional
# -------------------------

@app.route("/radar")
def radar():

    conn = conectar()
    c = conn.cursor()

    voos = c.execute("""
    SELECT helicopteros.prefixo,
           voos.hora,
           voos.duracao,
           voos.status
    FROM voos
    JOIN helicopteros
    ON voos.helicoptero_id = helicopteros.id
    WHERE voos.status != 'realizado'
    ORDER BY voos.hora
    """).fetchall()

    radar = []

    agora = datetime.now()

    for v in voos:

        hora_voo = datetime.strptime(v[1], "%H:%M")
        hora_voo = hora_voo.replace(
            year=agora.year,
            month=agora.month,
            day=agora.day
        )

        fim_voo = hora_voo + timedelta(minutes=v[2])

        if hora_voo <= agora <= fim_voo:
            estado = "VOANDO"

        elif agora < hora_voo:
            estado = "PRÓXIMO"

        elif agora > fim_voo:
            estado = "ATRASADO"

        else:
            estado = "SOLO"

        radar.append({
            "prefixo": v[0],
            "hora": v[1],
            "duracao": v[2],
            "estado": estado
        })

    conn.close()

    return render_template("radar.html", radar=radar)

    conn.close()

    return render_template("radar.html", radar=radar)


# -------------------------
# relatório diário
# -------------------------

@app.route("/relatorio")
def relatorio():

    hoje = str(date.today())

    conn = conectar()
    c = conn.cursor()

    relatorio = c.execute("""
    SELECT helicopteros.prefixo,
           COUNT(voos.id),
           SUM(voos.duracao),
           COALESCE(SUM(voos.combustivel_usado),0)
    FROM voos
    JOIN helicopteros
    ON voos.helicoptero_id = helicopteros.id
    WHERE voos.status='realizado'
    GROUP BY helicopteros.prefixo
    """).fetchall()

    conn.close()

    return render_template(
        "relatorio.html",
        relatorio=relatorio,
        hoje=hoje
    )


# -------------------------
# histórico
# -------------------------

@app.route("/historico")
def historico():

    conn = conectar()
    c = conn.cursor()

    historico = c.execute("""
    SELECT voos.id,
           helicopteros.prefixo,
           voos.data,
           voos.hora,
           voos.duracao,
           voos.combustivel_usado
    FROM voos
    JOIN helicopteros
    ON voos.helicoptero_id = helicopteros.id
    WHERE voos.status='realizado'
    ORDER BY voos.data DESC, voos.hora DESC
    """).fetchall()

    conn.close()

    return render_template(
        "historico.html",
        historico=historico
    )


# -------------------------
# iniciar servidor
# -------------------------

if __name__ == "__main__":
    app.run(debug=True)
