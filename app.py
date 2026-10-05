import os
import secrets
from functools import wraps
from pathlib import Path

import click
import pymysql
from dotenv import load_dotenv
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db

load_dotenv()

DIREITOS = {"S": "Supervisor", "O": "Operador"}
TIPOS = {"D": "Diária", "S": "Semanal", "Q": "Quinzenal", "M": "Mensal"}

app = Flask(__name__)
app.config.update(
    # Sem SECRET_KEY fixa, as sessões são invalidadas a cada reinício do servidor.
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    DB_HOST=os.environ.get("DB_HOST", "localhost"),
    DB_PORT=int(os.environ.get("DB_PORT", "3306")),
    DB_USER=os.environ.get("DB_USER", "root"),
    DB_PASSWORD=os.environ.get("DB_PASSWORD", ""),
    DB_NAME=os.environ.get("DB_NAME", "controle_tarefas"),
)
app.teardown_appcontext(db.close_db)


# ---------------------------------------------------------------- infraestrutura

@app.before_request
def carregar_usuario_e_validar_csrf():
    codigo = session.get("usuario")
    g.user = None
    if codigo:
        g.user = db.query(
            "SELECT codigo, nome, direito FROM usuario WHERE codigo = %s", (codigo,), one=True
        )
        if g.user is None:  # usuário excluído enquanto logado
            session.clear()

    if request.method == "POST":
        token = session.get("csrf")
        if not token or not secrets.compare_digest(token, request.form.get("csrf", "")):
            abort(400, "Token CSRF inválido. Recarregue a página e tente novamente.")


@app.context_processor
def variaveis_templates():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return {
        "csrf": session["csrf"],
        "TIPOS": TIPOS,
        "DIREITOS": DIREITOS,
        "supervisor": bool(g.get("user")) and g.user["direito"] == "S",
    }


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def supervisor_required(view):
    """RF005: somente supervisores cadastram tarefas/usuários ou designam tarefas."""
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user["direito"] != "S":
            abort(403, "Somente supervisores podem executar esta operação.")
        return view(*args, **kwargs)
    return wrapper


def validar_tarefa(nome, tipo):
    erros = []
    if not nome:
        erros.append("Informe o nome da tarefa.")
    elif len(nome) > 30:
        erros.append("O nome da tarefa deve ter no máximo 30 caracteres.")
    if tipo not in TIPOS:
        erros.append("Tipo de tarefa inválido.")
    return erros


def total_supervisores():
    return db.query("SELECT COUNT(*) AS n FROM usuario WHERE direito = 'S'", one=True)["n"]


# ---------------------------------------------------------------- login (RNF002)

@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "")
        user = db.query("SELECT codigo, senha FROM usuario WHERE nome = %s", (nome,), one=True)
        if user and check_password_hash(user["senha"], senha):
            session.clear()
            session["usuario"] = user["codigo"]
            return redirect(url_for("index"))
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- tela principal (RF003, RF004, RNF001)

@app.route("/")
@login_required
def index():
    usuarios = db.query("SELECT codigo, nome FROM usuario ORDER BY nome")
    cod_usuario = request.args.get("usuario", type=int) or g.user["codigo"]
    selecionado = next((u for u in usuarios if u["codigo"] == cod_usuario), None)
    if selecionado is None:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("index"))

    tipo = request.args.get("tipo", "")
    sql = (
        "SELECT t.codigo, t.nome, t.tipo FROM tarefa t "
        "JOIN usuario_tarefa ut ON ut.cod_tarefa = t.codigo "
        "WHERE ut.cod_usuario = %s"
    )
    args = [cod_usuario]
    if tipo in TIPOS:
        sql += " AND t.tipo = %s"
        args.append(tipo)
    tarefas = db.query(sql + " ORDER BY t.codigo", args)

    disponiveis = []
    if g.user["direito"] == "S":
        disponiveis = db.query(
            "SELECT codigo, nome, tipo FROM tarefa WHERE codigo NOT IN "
            "(SELECT cod_tarefa FROM usuario_tarefa WHERE cod_usuario = %s) ORDER BY nome",
            (cod_usuario,),
        )

    return render_template(
        "index.html",
        usuarios=usuarios,
        selecionado=selecionado,
        tipo=tipo,
        tarefas=tarefas,
        disponiveis=disponiveis,
    )


@app.post("/usuarios/<int:cod_usuario>/tarefas")
@supervisor_required
def designar_tarefas(cod_usuario):
    if not db.query("SELECT 1 FROM usuario WHERE codigo = %s", (cod_usuario,), one=True):
        abort(404)

    codigos = [int(c) for c in request.form.getlist("tarefas") if c.isdigit()]
    nome = request.form.get("nova_nome", "").strip()
    tipo = request.form.get("nova_tipo", "")

    # Criação rápida de uma nova tarefa já designada ao usuário, na mesma tela (RF004).
    if nome:
        erros = validar_tarefa(nome, tipo)
        if erros:
            for e in erros:
                flash(e, "erro")
            return redirect(url_for("index", usuario=cod_usuario))
        codigos.append(db.execute("INSERT INTO tarefa (nome, tipo) VALUES (%s, %s)", (nome, tipo)))

    if not codigos:
        flash("Selecione ao menos uma tarefa ou informe uma nova.", "erro")
        return redirect(url_for("index", usuario=cod_usuario))

    existentes = {
        r["codigo"]
        for r in db.query(
            "SELECT codigo FROM tarefa WHERE codigo IN (%s)" % ",".join(["%s"] * len(codigos)), codigos
        )
    }
    db.execute_many(
        "INSERT IGNORE INTO usuario_tarefa (cod_usuario, cod_tarefa) VALUES (%s, %s)",
        [(cod_usuario, c) for c in existentes],
    )
    flash(f"{len(existentes)} tarefa(s) incluída(s).", "ok")
    return redirect(url_for("index", usuario=cod_usuario))


@app.post("/usuarios/<int:cod_usuario>/tarefas/<int:cod_tarefa>/remover")
@supervisor_required
def remover_tarefa_usuario(cod_usuario, cod_tarefa):
    db.execute(
        "DELETE FROM usuario_tarefa WHERE cod_usuario = %s AND cod_tarefa = %s",
        (cod_usuario, cod_tarefa),
    )
    flash("Tarefa removida do usuário.", "ok")
    return redirect(url_for("index", usuario=cod_usuario))


# ---------------------------------------------------------------- cadastro de tarefas (RF001)

@app.route("/tarefas")
@supervisor_required
def tarefas():
    editar = request.args.get("editar", type=int)
    tarefa = None
    if editar:
        tarefa = db.query("SELECT codigo, nome, tipo FROM tarefa WHERE codigo = %s", (editar,), one=True)
        if tarefa is None:
            flash("Tarefa não encontrada.", "erro")
    lista = db.query(
        "SELECT t.codigo, t.nome, t.tipo, COUNT(ut.cod_usuario) AS usuarios FROM tarefa t "
        "LEFT JOIN usuario_tarefa ut ON ut.cod_tarefa = t.codigo "
        "GROUP BY t.codigo, t.nome, t.tipo ORDER BY t.codigo"
    )
    return render_template("tarefas.html", lista=lista, tarefa=tarefa)


@app.post("/tarefas/salvar")
@supervisor_required
def salvar_tarefa():
    codigo = request.form.get("codigo", type=int)
    nome = request.form.get("nome", "").strip()
    tipo = request.form.get("tipo", "")
    erros = validar_tarefa(nome, tipo)
    if erros:
        for e in erros:
            flash(e, "erro")
        return redirect(url_for("tarefas", editar=codigo) if codigo else url_for("tarefas"))

    if codigo:
        db.execute("UPDATE tarefa SET nome = %s, tipo = %s WHERE codigo = %s", (nome, tipo, codigo))
        flash("Tarefa alterada.", "ok")
    else:
        codigo = db.execute("INSERT INTO tarefa (nome, tipo) VALUES (%s, %s)", (nome, tipo))
        flash(f"Tarefa {codigo} cadastrada.", "ok")
    return redirect(url_for("tarefas"))


@app.post("/tarefas/<int:codigo>/excluir")
@supervisor_required
def excluir_tarefa(codigo):
    db.execute("DELETE FROM tarefa WHERE codigo = %s", (codigo,))
    flash("Tarefa excluída.", "ok")
    return redirect(url_for("tarefas"))


# ---------------------------------------------------------------- cadastro de usuários (RF002)

@app.route("/usuarios")
@supervisor_required
def usuarios():
    editar = request.args.get("editar", type=int)
    usuario = None
    if editar:
        usuario = db.query(
            "SELECT codigo, nome, direito FROM usuario WHERE codigo = %s", (editar,), one=True
        )
        if usuario is None:
            flash("Usuário não encontrado.", "erro")
    lista = db.query("SELECT codigo, nome, direito FROM usuario ORDER BY codigo")
    return render_template("usuarios.html", lista=lista, usuario=usuario)


@app.post("/usuarios/salvar")
@supervisor_required
def salvar_usuario():
    codigo = request.form.get("codigo", type=int)
    nome = request.form.get("nome", "").strip()
    direito = request.form.get("direito", "")
    senha = request.form.get("senha", "")
    confirmacao = request.form.get("confirmacao", "")

    atual = None
    if codigo:
        atual = db.query("SELECT codigo, direito FROM usuario WHERE codigo = %s", (codigo,), one=True)
        if atual is None:
            abort(404)

    erros = []
    if not nome:
        erros.append("Informe o nome do usuário.")
    elif len(nome) > 50:
        erros.append("O nome deve ter no máximo 50 caracteres.")
    if direito not in DIREITOS:
        erros.append("Direito inválido.")
    if not codigo and not senha:
        erros.append("Informe a senha.")
    if senha != confirmacao:
        erros.append("A confirmação de senha não confere.")
    if atual and atual["direito"] == "S" and direito == "O" and total_supervisores() <= 1:
        erros.append("O sistema precisa de ao menos um supervisor.")

    if not erros:
        try:
            if codigo:
                if senha:
                    db.execute(
                        "UPDATE usuario SET nome = %s, direito = %s, senha = %s WHERE codigo = %s",
                        (nome, direito, generate_password_hash(senha), codigo),
                    )
                else:
                    db.execute(
                        "UPDATE usuario SET nome = %s, direito = %s WHERE codigo = %s",
                        (nome, direito, codigo),
                    )
                flash("Usuário alterado.", "ok")
            else:
                codigo = db.execute(
                    "INSERT INTO usuario (nome, direito, senha) VALUES (%s, %s, %s)",
                    (nome, direito, generate_password_hash(senha)),
                )
                flash(f"Usuário {codigo} cadastrado.", "ok")
            return redirect(url_for("usuarios"))
        except pymysql.err.IntegrityError:
            erros.append("Já existe um usuário com esse nome.")

    for e in erros:
        flash(e, "erro")
    return redirect(url_for("usuarios", editar=codigo) if codigo else url_for("usuarios"))


@app.post("/usuarios/<int:codigo>/excluir")
@supervisor_required
def excluir_usuario(codigo):
    alvo = db.query("SELECT direito FROM usuario WHERE codigo = %s", (codigo,), one=True)
    if alvo is None:
        abort(404)
    if codigo == g.user["codigo"]:
        flash("Você não pode excluir o próprio usuário.", "erro")
    elif alvo["direito"] == "S" and total_supervisores() <= 1:
        flash("O sistema precisa de ao menos um supervisor.", "erro")
    else:
        db.execute("DELETE FROM usuario WHERE codigo = %s", (codigo,))
        flash("Usuário excluído.", "ok")
    return redirect(url_for("usuarios"))


# ---------------------------------------------------------------- comando de instalação

@app.cli.command("init-db")
@click.option("--admin", default="admin", show_default=True, help="Nome do supervisor inicial.")
@click.option("--senha", prompt="Senha do supervisor inicial", hide_input=True,
              confirmation_prompt=True, help="Senha do supervisor inicial.")
def init_db(admin, senha):
    """Cria o banco, as tabelas e o primeiro supervisor (se não houver nenhum)."""
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    nome_db = app.config["DB_NAME"]
    conn = db.connect(database=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{nome_db}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.execute(f"USE `{nome_db}`")
            for comando in schema.split(";"):
                linhas = [l for l in comando.splitlines() if not l.strip().startswith("--")]
                if "".join(linhas).strip():
                    cur.execute("\n".join(linhas))
            cur.execute("SELECT COUNT(*) AS n FROM usuario WHERE direito = 'S'")
            if cur.fetchone()["n"] == 0:
                cur.execute(
                    "INSERT INTO usuario (nome, direito, senha) VALUES (%s, 'S', %s)",
                    (admin, generate_password_hash(senha)),
                )
                click.echo(f"Supervisor '{admin}' criado.")
            else:
                click.echo("Já existe supervisor; nenhum usuário foi criado.")
        conn.commit()
    finally:
        conn.close()
    click.echo(f"Banco '{nome_db}' pronto.")


if __name__ == "__main__":
    app.run(debug=True)
