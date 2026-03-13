from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3

import os
from uuid import uuid4
from werkzeug.utils import secure_filename

import pandas as pd
from flask import send_file
import io
#from flask_mail import Mail, Message
#app.config['MAIL_SERVER'] = 'smtp.gmail.com'
#app.config['MAIL_PORT'] = 587
#app.config['MAIL_USE_TLS'] = True
#app.config['MAIL_USERNAME'] = 'TEUEMAIL@gmail.com'
#app.config['MAIL_PASSWORD'] = 'PASSWORD_APP_GMAIL'

#mail = Mail(app)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file_storage, subfolder: str):
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None

    os.makedirs(os.path.join("uploads", subfolder), exist_ok=True)

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[1].lower()
    new_name = f"{uuid4().hex}.{ext}"

    disk_path = os.path.join("uploads", subfolder, new_name)
    file_storage.save(disk_path)

    return f"/uploads/{subfolder}/{new_name}"


# Garante que o Flask consegue ler ficheiros na raiz (como a pasta IMG e o style.css)
app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = "altera-esta-secret-key"


def get_connection():
    """Abre uma ligação ao SQLite (ficheiro local)."""
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    return conn

def log_action(action, entity, entity_id=None, details=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO logs (user_id, user_email, action, entity, entity_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        session.get("user_id"),
        session.get("user_email"),
        action,
        entity,
        entity_id,
        details
    ))
    conn.commit()
    conn.close()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trabalhadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            imagem TEXT
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/servicos")
def servicos():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titulo, descricao, imagem FROM servicos ORDER BY id ASC")
        servicos = cursor.fetchall()
    except Exception as e:
        flash(f"Erro ao carregar serviços: {e}", "danger")
        servicos = []
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return render_template("servicos.html", servicos=servicos)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            query = """
            SELECT id, nome, email, role
            FROM trabalhadores
            WHERE email = ? AND password = ?
            """
            cursor.execute(query, (email, password))
            user = cursor.fetchone()

            if user:
                session["user_id"] = user["id"]
                session["user_name"] = user["nome"]
                session["user_email"] = user["email"]
                session["user_role"] = user["role"]
                return redirect(url_for("dashboard"))
            else:
                flash("Email ou palavra-passe inválidos.", "danger")

        except Exception as e:
            flash(f"Erro na ligação à base de dados: {e}", "danger")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    return render_template("login.html")


def login_required(view_func):
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    wrapper.__name__ = view_func.__name__
    return wrapper


@app.route("/admin/servicos")
@login_required
def admin_servicos():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titulo, descricao, imagem FROM servicos ORDER BY id ASC")
        servicos = cursor.fetchall()
    except Exception as e:
        flash(f"Erro ao carregar serviços: {e}", "danger")
        servicos = []
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return render_template("admin_servicos.html", servicos=servicos)


@app.route("/admin/servicos/novo", methods=["GET", "POST"])
@login_required
def admin_servico_novo():
    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        imagem_path = save_upload(request.files.get("imagem"), "servicos")


        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
    "INSERT INTO servicos (titulo, descricao, imagem, created_at) VALUES (?, ?, ?, datetime('now'))",
    (titulo, descricao, imagem_path),


            )
            conn.commit()
            new_id = cursor.lastrowid
            log_action("CREATE", "servico", new_id, f"titulo={titulo}")

            flash("Serviço criado com sucesso.", "success")
            return redirect(url_for("admin_servicos"))
        except Exception as e:
            flash(f"Erro ao criar serviço: {e}", "danger")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    return render_template("admin_servico_form.html", servico=None)


@app.route("/admin/servicos/<int:servico_id>/editar", methods=["GET", "POST"])
@login_required
def admin_servico_editar(servico_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, titulo, descricao, imagem FROM servicos WHERE id = ?",
            (servico_id,),
        )
        servico = cursor.fetchone()
    except Exception as e:
        flash(f"Erro ao carregar serviço: {e}", "danger")
        servico = None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if servico is None:
        flash("Serviço não encontrado.", "danger")
        return redirect(url_for("admin_servicos"))

    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        imagem = request.form.get("imagem")

        nova = save_upload(request.files.get("imagem"), "servicos")
        if not nova:
            nova = servico["imagem"]  # mantém a imagem antiga

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE servicos SET titulo = ?, descricao = ?, imagem = ? WHERE id = ?",
                (titulo, descricao, imagem, servico_id),
            )
            conn.commit()
            log_action("UPDATE", "servico", servico_id, f"titulo={titulo}")
            flash("Serviço atualizado com sucesso.", "success")
            return redirect(url_for("admin_servicos"))
        except Exception as e:
            flash(f"Erro ao atualizar serviço: {e}", "danger")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    return render_template("admin_servico_form.html", servico=servico)


@app.route("/admin/servicos/<int:servico_id>/remover", methods=["POST"])
@login_required
def admin_servico_remover(servico_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM servicos WHERE id = ?", (servico_id,))
        conn.commit()
        log_action("DELETE", "servico", servico_id)
        flash("Serviço removido com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao remover serviço: {e}", "danger")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return redirect(url_for("admin_servicos"))


@app.route("/dashboard")
@login_required
def dashboard():
    total_servicos = 0
    total_trabalhadores = 0
    total_equipa = 0
    pendentes = 0
    tratados = 0

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Contagem de Serviços
        cursor.execute("SELECT COUNT(*) as total FROM servicos")
        total_servicos = cursor.fetchone()["total"]

        # Contagem de Trabalhadores (Acessos)
        cursor.execute("SELECT COUNT(*) as total FROM trabalhadores")
        total_trabalhadores = cursor.fetchone()["total"]
        
        # Contagem de Membros da Equipa
        cursor.execute("SELECT COUNT(*) as total FROM equipa")
        total_equipa = cursor.fetchone()["total"]

        # Dados para o Gráfico (Tabela pedidos_orcamento)
        cursor.execute("SELECT COUNT(*) FROM pedidos_orcamento WHERE tratado = 0")
        pendentes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM pedidos_orcamento WHERE tratado = 1")
        tratados = cursor.fetchone()[0]

    except Exception as e:
        flash(f"Erro a carregar dados do painel: {e}", "danger")
    finally:
        if conn: conn.close()

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name"),
        total_servicos=total_servicos,
        total_trabalhadores=total_trabalhadores,
        total_equipa=total_equipa,
        pendentes=pendentes,
        tratados=tratados,
        total_pedidos=pendentes + tratados
    )


@app.route("/sobre")
def sobre():
    return render_template("sobre.html")


@app.route("/contactos")
def contactos():
    return render_template("contactos.html")

@app.route("/equipa")
def equipa():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nome, cargo, descricao, foto
        FROM equipa
        WHERE ativo = 1
        ORDER BY id ASC
    """)
    equipa_lista = cursor.fetchall()
    conn.close()
    return render_template("equipa.html", equipa=equipa_lista)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin/equipa")
@login_required
def admin_equipa():
    if session.get("user_role") != "admin":
        flash("Sem permissões de administração.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, cargo, descricao, foto, ativo FROM equipa ORDER BY id ASC")
    membros = cursor.fetchall()
    conn.close()

    return render_template("admin_equipa.html", membros=membros)


@app.route("/admin/equipa/novo", methods=["GET", "POST"])
@login_required
def admin_equipa_novo():
    if session.get("user_role") != "admin":
        flash("Sem permissões de administração.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nome = request.form.get("nome")
        cargo = request.form.get("cargo")
        descricao = request.form.get("descricao")
        foto_path = save_upload(request.files.get("foto"), "equipa")
        ativo = 1 if request.form.get("ativo") == "1" else 0

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO equipa (nome, cargo, descricao, foto, ativo) VALUES        (?, ?, ?, ?, 1)",
            (nome, cargo, descricao, foto_path),
        )

        conn.commit()
        conn.close()

        flash("Membro adicionado com sucesso.", "success")
        return redirect(url_for("admin_equipa"))

    return render_template("admin_equipa_form.html", membro=None)

@app.route("/admin/equipa/<int:membro_id>/editar", methods=["GET", "POST"])
@login_required
def admin_equipa_editar(membro_id):
    if session.get("user_role") != "admin":
        flash("Sem permissões de administração.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, cargo, descricao, foto, ativo FROM equipa WHERE id = ?", (membro_id,))
    membro = cursor.fetchone()

    if not membro:
        conn.close()
        flash("Membro não encontrado.", "danger")
        return redirect(url_for("admin_equipa"))

    if request.method == "POST":
        nome = request.form.get("nome")
        cargo = request.form.get("cargo")
        descricao = request.form.get("descricao")
        foto = request.form.get("foto")
        ativo = 1 if request.form.get("ativo") == "1" else 0

        cursor.execute(
            "UPDATE equipa SET nome=?, cargo=?, descricao=?, foto=?, ativo=? WHERE id=?",
            (nome, cargo, descricao, foto, ativo, membro_id),
        )
        conn.commit()
        conn.close()

        flash("Membro atualizado com sucesso.", "success")
        return redirect(url_for("admin_equipa"))

    conn.close()
    return render_template("admin_equipa_form.html", membro=membro)

@app.route("/admin/equipa/<int:membro_id>/toggle", methods=["POST"])
@login_required
def admin_equipa_toggle(membro_id):
    if session.get("user_role") != "admin":
        flash("Sem permissões de administração.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE equipa SET ativo = CASE WHEN ativo=1 THEN 0 ELSE 1 END WHERE id=?", (membro_id,))
    conn.commit()
    conn.close()

    flash("Estado do membro atualizado.", "success")
    return redirect(url_for("admin_equipa"))

from flask import jsonify

@app.route("/api/stats/servicos_por_dia")
@login_required
def stats_servicos_por_dia():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT substr(COALESCE(created_at, datetime('now')), 1, 10) as dia,
        COUNT(*) as total
        FROM servicos
        GROUP BY dia
        ORDER BY dia ASC
        LIMIT 30
    """)
    rows = cursor.fetchall()
    conn.close()

    labels = [r["dia"] for r in rows]
    data = [r["total"] for r in rows]
    return jsonify({"labels": labels, "data": data})

def log_action(action: str, entity: str, entity_id: int | None = None, details: str | None = None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (user_id, user_email, action, entity, entity_id, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session.get("user_id"),
            session.get("user_email"),
            action,
            entity,
            entity_id,
            details
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass

@app.route("/admin/logs")
@login_required
def admin_logs():
    if session.get("user_role") != "admin":
        flash("Sem permissões de administração.", "danger")
        return redirect(url_for("dashboard"))

    # filtros
    q = request.args.get("q", "").strip()
    action = request.args.get("action", "").strip()   # CREATE/UPDATE/DELETE
    entity = request.args.get("entity", "").strip()   # servico/equipa/...

    # paginação
    page = request.args.get("page", 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    where = []
    params = []

    if q:
        where.append("(user_email LIKE ? OR details LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])

    if action:
        where.append("action = ?")
        params.append(action)

    if entity:
        where.append("entity = ?")
        params.append(entity)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = get_connection()
    cursor = conn.cursor()

    # total
    cursor.execute(f"SELECT COUNT(*) AS total FROM logs {where_sql}", params)
    total = cursor.fetchone()["total"]
    total_pages = (total + per_page - 1) // per_page if total else 1

    # dados da página
    cursor.execute(f"""
        SELECT id, user_email, action, entity, entity_id, details, created_at
        FROM logs
        {where_sql}
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])

    logs = cursor.fetchall()

    # opções para dropdowns (tiradas da própria BD)
    cursor.execute("SELECT DISTINCT action FROM logs ORDER BY action")
    actions = [r["action"] for r in cursor.fetchall() if r["action"]]

    cursor.execute("SELECT DISTINCT entity FROM logs ORDER BY entity")
    entities = [r["entity"] for r in cursor.fetchall() if r["entity"]]

    conn.close()

    return render_template("admin_logs.html",
        logs=logs,
        page=page,
        total_pages=total_pages,
        total=total,
        q=q,
        action=action,
        entity=entity,
        actions=actions,
        entities=entities,
    )

@app.route("/servico/<int:servico_id>")
def servico_detalhe(servico_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM servicos WHERE id = ?", (servico_id,))
    servico = cursor.fetchone()
    conn.close()

    if not servico: 
        abort(404)

    return render_template("servico_detalhe.html", servico=servico)

@app.route("/pedido-orcamento", methods=["POST"])
def pedido_orcamento():
    nome = request.form.get("nome")
    email = request.form.get("email")
    mensagem = request.form.get("mensagem")
    servico_id = request.form.get("servico_id")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO pedidos_orcamento (nome, email, mensagem, servico_id)
        VALUES (?, ?, ?, ?)
    """, (nome, email, mensagem, servico_id))

    conn.commit()
    conn.close()

    flash("Pedido enviado com sucesso! Entraremos em contacto.", "success")
    return redirect(url_for("servicos"))


@app.route("/admin/pedidos/<int:pedido_id>/tratar")
@login_required
def admin_pedido_tratar(pedido_id):
    if session.get("user_role") != "admin":
        flash("Sem permissões.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE pedidos_orcamento SET tratado = 1 WHERE id = ?", (pedido_id,))
    conn.commit()
    conn.close()

    flash("Pedido marcado como tratado.", "success")
    return redirect(url_for("admin_pedidos"))

@app.route("/admin/pedidos")
@login_required
def admin_pedidos():
    if session.get("user_role") != "admin":
        return redirect(url_for("dashboard"))

    # Pega o filtro da URL (ex: /admin/pedidos?estado=1)
    filtro_estado = request.args.get('estado')

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT p.*, s.titulo AS servico_nome
        FROM pedidos_orcamento p
        LEFT JOIN servicos s ON p.servico_id = s.id
    """
    
    params = []
    if filtro_estado in ['0', '1']:
        query += " WHERE p.tratado = ?"
        params.append(filtro_estado)

    query += " ORDER BY p.id DESC"
    
    cursor.execute(query, params)
    pedidos = cursor.fetchall()
    conn.close()

    return render_template("admin_pedidos.html", pedidos=pedidos, filtro_atual=filtro_estado)

@app.route("/admin/pedidos/exportar")
@login_required
def exportar_pedidos():
    if session.get("user_role") != "admin":
        return redirect(url_for("dashboard"))

    conn = get_connection()
    # Query para buscar os dados
    query = """
        SELECT p.id, p.created_at as Data, p.nome as Cliente, p.email as Email, 
               s.titulo as Servico, p.mensagem as Mensagem,
               CASE WHEN p.tratado = 1 THEN 'Sim' ELSE 'Não' END as Tratado
        FROM pedidos_orcamento p
        LEFT JOIN servicos s ON p.servico_id = s.id
        ORDER BY p.id DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Criar um ficheiro Excel em memória (sem precisar de guardar no disco do PC)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Pedidos')
    
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="pedidos_visreci.xlsx"
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)


