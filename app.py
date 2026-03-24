from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, make_response
import sqlite3
import os
import io
import math
import pandas as pd
from uuid import uuid4
from werkzeug.utils import secure_filename
from flask import send_file
#import openpyxl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps

# Configurações do teu email (Exemplo Gmail)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "visreciteste@gmail.com"
EMAIL_PASS = "cugr blil vges lvxh"

def enviar_email(destinatario, assunto, corpo):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Segurança
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = "altera-esta-secret-key"

# --- CONFIGURAÇÕES DE UPLOADS ---
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file_storage, subfolder):
    if not file_storage or file_storage.filename == "": return None
    if not allowed_file(file_storage.filename): return None
    os.makedirs(os.path.join("uploads", subfolder), exist_ok=True)
    filename = secure_filename(file_storage.filename)
    new_name = f"{uuid4().hex}.{filename.rsplit('.', 1)[1].lower()}"
    disk_path = os.path.join("uploads", subfolder, new_name)
    file_storage.save(disk_path)
    return f"/uploads/{subfolder}/{new_name}"

# --- BASE DE DADOS E LOGS ---

def get_connection():
    # Adicionamos o timeout de 20 ou 30 segundos
    conn = sqlite3.connect("app.db", timeout=30) 
    conn.row_factory = sqlite3.Row
    return conn

def log_action(action, entity, entity_id=None, details=None):
    """Regista uma ação na tabela de logs"""
    try:
        conn = get_connection()
        conn.execute("""
            INSERT INTO logs (user_id, user_email, action, entity, entity_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        """, (session.get("user_id"), session.get("user_email"), action, entity, entity_id, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao gravar log: {e}")

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Criar Tabela de Logs (Garante todas as colunas necessárias)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_email TEXT,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT,
            created_at DATETIME
        )
    """)

    # Criar Tabela de Trabalhadores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trabalhadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'admin'
        )
    """)

    # Criar Tabela de Serviços
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            descricao TEXT,
            imagem TEXT,
            created_at DATETIME DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Criar Tabela de Equipa
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            cargo TEXT,
            descricao TEXT,
            foto TEXT,
            ativo INTEGER DEFAULT 1
        )
    """)

    # Criar Tabela de Pedidos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos_orcamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT,
            mensagem TEXT,
            servico_id INTEGER,
            tratado INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT (datetime('now', 'localtime'))
        )
        
    """)

    # Tabela de Reclamações
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reclamacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            assunto TEXT,
            mensagem TEXT NOT NULL,
            estado TEXT DEFAULT 'Pendente',
            created_at DATETIME DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Criar utilizadores iniciais se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) FROM trabalhadores")
    if cursor.fetchone()[0] == 0:
        utilizadores = [
            ('Rodrigo', 'rodrigo@email.com', '1234', 'admin'),
            ('Lucas', 'lucas@email.com', '1234', 'admin')
        ]
        cursor.executemany("""
            INSERT INTO trabalhadores (nome, email, password, role) 
            VALUES (?, ?, ?, ?)
        """, utilizadores)
        print("✅ Utilizadores da equipa criados com sucesso!")

    conn.commit()
    conn.close()

# def login_required(view_func):
#     def wrapper(*args, **kwargs):
#         if "user_id" not in session: return redirect(url_for("login"))
#         return view_func(*args, **kwargs)
#     wrapper.__name__ = view_func.__name__
#     return wrapper

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper

# --- ROTAS PÚBLICAS ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/servicos")
def servicos():
    conn = get_connection()
    servicos = conn.execute("SELECT * FROM servicos ORDER BY id ASC").fetchall()
    conn.close()
    return render_template("servicos.html", servicos=servicos)

@app.route("/servico/<int:servico_id>")
def servico_detalhe(servico_id):
    conn = get_connection()
    servico = conn.execute("SELECT * FROM servicos WHERE id = ?", (servico_id,)).fetchone()
    conn.close()
    if not servico: abort(404)
    return render_template("servico_detalhe.html", servico=servico)

@app.route("/sobre")
def sobre():
    conn = get_connection()
    equipa_lista = conn.execute("SELECT * FROM equipa WHERE ativo = 1").fetchall()
    conn.close()
    return render_template("sobre.html", equipa=equipa_lista)

@app.route("/equipa")
def equipa():
    conn = get_connection()
    equipa_lista = conn.execute("SELECT * FROM equipa WHERE ativo = 1 ORDER BY id ASC").fetchall()
    conn.close()
    return render_template("equipa.html", equipa=equipa_lista)

@app.route("/contactos", methods=["GET", "POST"])
def contactos():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        assunto = request.form.get("assunto")
        mensagem = request.form.get("mensagem")

        # 1. Guarda na Base de Dados (Opcional, mas recomendado)
        conn = get_connection()
        conn.execute("INSERT INTO contactos (nome, email, assunto, mensagem) VALUES (?, ?, ?, ?)",
                     (nome, email, assunto, mensagem))
        conn.commit()
        conn.close()

        # 2. Envia o Email Automático (Igual ao que tens nas reclamações)
        corpo = f"<h2>Novo Contacto de {nome}</h2><p>Assunto: {assunto}</p><p>Mensagem: {mensagem}</p>"
        enviar_email(EMAIL_USER, f"CONTACTO: {assunto}", corpo)

        flash("Mensagem enviada com sucesso!", "success")
        return redirect(url_for("contactos")) # Volta para a página de contacto
        
    return render_template("contactos.html")


@app.route("/admin/contactos")
@login_required
def admin_contactos():
    conn = get_connection()
    mensagens = conn.execute("SELECT * FROM contactos ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin_contactos.html", mensagens=mensagens)

# --- AUTENTICAÇÃO ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email, password = request.form.get("email"), request.form.get("password")
        conn = get_connection()
        user = conn.execute("SELECT * FROM trabalhadores WHERE email = ? AND password = ?", (email, password)).fetchone()
        conn.close()
        if user:
            session.update({"user_id": user["id"], "user_name": user["nome"], "user_email": user["email"], "user_role": user["role"]})
            log_action("LOGIN", "SISTEMA", details=f"O administrador {user['nome']} entrou no painel.")
            return redirect(url_for("dashboard"))
        flash("Email ou palavra-passe inválidos.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    log_action("LOGOUT", "SISTEMA", details="Encerrou a sessão.")
    session.clear()
    return redirect(url_for("login"))

# --- ADMIN DASHBOARD ---

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    
    # Contagens de Recursos
    total_servicos = conn.execute("SELECT COUNT(*) FROM servicos").fetchone()[0]
    total_trabalhadores = conn.execute("SELECT COUNT(*) FROM trabalhadores").fetchone()[0]
    total_equipa = conn.execute("SELECT COUNT(*) FROM equipa").fetchone()[0]
    
    # Gestão de Orçamentos (Substitui a lógica de queixas)
    pendentes = conn.execute("SELECT COUNT(*) FROM pedidos_orcamento WHERE tratado = 0").fetchone()[0]
    tratados = conn.execute("SELECT COUNT(*) FROM pedidos_orcamento WHERE tratado = 1").fetchone()[0]
    total_pedidos = pendentes + tratados

    # --- LÓGICA DO GRÁFICO (Agora focado em Pedidos de Orçamento) ---
    # Vamos buscar o volume de pedidos dos últimos meses para o gráfico
    stats_query = """
        SELECT strftime('%m', created_at) as mes, COUNT(*) as total 
        FROM pedidos_orcamento 
        GROUP BY mes 
        ORDER BY mes ASC 
        LIMIT 6
    """
    stats_rows = conn.execute(stats_query).fetchall()
    
    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    # Se não houver dados, enviamos listas vazias para não dar erro
    labels_grafico = [meses_nomes[int(r['mes'])-1] for r in stats_rows] if stats_rows else ["Sem dados"]
    dados_grafico = [r['total'] for r in stats_rows] if stats_rows else [0]
    
    conn.close()
    
    return render_template("dashboard.html", 
                        user_name=session.get("user_name"),
                        total_servicos=total_servicos,
                        total_trabalhadores=total_trabalhadores,
                        total_equipa=total_equipa,
                        pendentes=pendentes,
                        tratados=tratados,
                        total_pedidos=total_pedidos,
                        labels_grafico=labels_grafico,
                        dados_grafico=dados_grafico)

@app.route("/admin/servicos")
@login_required
def admin_servicos():
    conn = get_connection()
    servicos = conn.execute("SELECT * FROM servicos ORDER BY id ASC").fetchall()
    conn.close()
    return render_template("admin_servicos.html", servicos=servicos)

@app.route("/admin/servicos/novo", methods=["GET", "POST"])
@login_required
def admin_servico_novo():
    if request.method == "POST":
        titulo, desc = request.form.get("titulo"), request.form.get("descricao")
        img = save_upload(request.files.get("imagem"), "servicos")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO servicos (titulo, descricao, imagem) VALUES (?, ?, ?)", (titulo, desc, img))
        conn.commit()
        new_id = cursor.lastrowid
        log_action("CREATE", "SERVICO", new_id, f"Título: {titulo}")
        conn.close()
        flash("Serviço criado!", "success")
        return redirect(url_for("admin_servicos"))
    return render_template("admin_servico_form.html", servico=None)

@app.route("/admin/servicos/<int:servico_id>/editar", methods=["GET", "POST"])
@login_required
def admin_servico_editar(servico_id):
    conn = get_connection()
    servico = conn.execute("SELECT * FROM servicos WHERE id = ?", (servico_id,)).fetchone()
    if request.method == "POST":
        titulo, desc = request.form.get("titulo"), request.form.get("descricao")
        nova_img = save_upload(request.files.get("imagem"), "servicos") or servico["imagem"]
        conn.execute("UPDATE servicos SET titulo=?, descricao=?, imagem=? WHERE id=?", (titulo, desc, nova_img, servico_id))
        conn.commit()
        log_action("UPDATE", "SERVICO", servico_id, f"Editou: {titulo}")
        conn.close()
        flash("Serviço atualizado!", "success")
        return redirect(url_for("admin_servicos"))
    conn.close()
    return render_template("admin_servico_form.html", servico=servico)

@app.route("/admin/servicos/<int:servico_id>/remover", methods=["POST"])
@login_required
def admin_servico_remover(servico_id):
    conn = get_connection()
    conn.execute("DELETE FROM servicos WHERE id = ?", (servico_id,))
    conn.commit()
    log_action("DELETE", "SERVICO", servico_id, "Serviço removido")
    conn.close()
    flash("Serviço removido.", "success")
    return redirect(url_for("admin_servicos"))

# --- GESTÃO DE EQUIPA ---

@app.route("/admin/equipa")
@login_required
def admin_equipa():
    conn = get_connection()
    membros = conn.execute("SELECT * FROM equipa ORDER BY id ASC").fetchall()
    conn.close()
    return render_template("admin_equipa.html", membros=membros)

@app.route("/admin/equipa/novo", methods=["GET", "POST"])
@login_required
def admin_equipa_novo():
    if request.method == "POST":
        nome, cargo, desc = request.form.get("nome"), request.form.get("cargo"), request.form.get("descricao")
        foto = save_upload(request.files.get("foto"), "equipa")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO equipa (nome, cargo, descricao, foto, ativo) VALUES (?, ?, ?, ?, 1)", (nome, cargo, desc, foto))
        conn.commit()
        new_id = cursor.lastrowid
        log_action("CREATE", "EQUIPA", new_id, f"Adicionou {nome}")
        conn.close()
        flash("Membro adicionado!", "success")
        return redirect(url_for("admin_equipa"))
    return render_template("admin_equipa_form.html", membro=None)

@app.route("/admin/equipa/<int:membro_id>/editar", methods=["GET", "POST"])
@login_required
def admin_equipa_editar(membro_id):
    conn = get_connection()
    membro = conn.execute("SELECT * FROM equipa WHERE id = ?", (membro_id,)).fetchone()
    if request.method == "POST":
        nome = request.form.get("nome")
        cargo = request.form.get("cargo")
        desc = request.form.get("descricao")
        ativo = 1 if request.form.get("ativo") == "1" else 0
        
        # Lógica para a foto na edição
        nova_foto = request.files.get("foto")
        if nova_foto and nova_foto.filename != '':
            foto_nome = save_upload(nova_foto, "equipa")
            conn.execute("UPDATE equipa SET nome=?, cargo=?, descricao=?, foto=?, ativo=? WHERE id=?", 
                        (nome, cargo, desc, foto_nome, ativo, membro_id))
        else:
            conn.execute("UPDATE equipa SET nome=?, cargo=?, descricao=?, ativo=? WHERE id=?", 
            (nome, cargo, desc, ativo, membro_id))
        conn.commit()
        conn.close()
        flash("Membro atualizado!", "success")
        return redirect(url_for("admin_equipa"))
    conn.close()
    return render_template("admin_equipa_form.html", membro=membro)
@app.route("/admin/equipa/<int:membro_id>/toggle", methods=["POST"])
@login_required
def admin_equipa_toggle(membro_id):
    conn = get_connection()
    conn.execute("UPDATE equipa SET ativo = CASE WHEN ativo=1 THEN 0 ELSE 1 END WHERE id=?", (membro_id,))
    conn.commit()
    log_action("UPDATE", "EQUIPA", membro_id, "Alterou estado Ativo/Inativo")
    conn.close()
    return redirect(url_for("admin_equipa"))

# --- LOGS COM PAGINAÇÃO ---

@app.route("/admin/logs")
@login_required
def admin_logs():
    if session.get("user_role") != "admin": return redirect(url_for("dashboard"))
    page, q = request.args.get('page', 1, type=int), request.args.get('q', '').strip()
    act_f, ent_f = request.args.get('action', '').strip(), request.args.get('entity', '').strip()
    
    per_page = 10
    where, params = [], []
    if q: where.append("(user_email LIKE ? OR details LIKE ?)"); p = f"%{q}%"; params.extend([p, p])
    if act_f: where.append("action = ?"); params.append(act_f)
    if ent_f: where.append("entity = ?"); params.append(ent_f)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    
    conn = get_connection()
    total = conn.execute(f"SELECT COUNT(*) FROM logs {where_sql}", params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))
    logs = conn.execute(f"SELECT * FROM logs {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?", params + [per_page, (page-1)*per_page]).fetchall()
    
    actions = [r[0] for r in conn.execute("SELECT DISTINCT action FROM logs WHERE action IS NOT NULL").fetchall()]
    entities = [r[0] for r in conn.execute("SELECT DISTINCT entity FROM logs WHERE entity IS NOT NULL").fetchall()]
    conn.close()
    return render_template("admin_logs.html", logs=logs, page=page, total_pages=total_pages, q=q, action=act_f, entity=ent_f, actions=actions, entities=entities)

# --- PEDIDOS DE ORÇAMENTO ---

@app.route("/pedir_orcamento", methods=["POST"])
def pedir_orcamento():
    nome = request.form.get("nome")
    email = request.form.get("email")
    telefone = request.form.get("telefone")
    servico_id = request.form.get("servico_id")
    mensagem = request.form.get("mensagem")

    conn = get_connection()
    cursor = conn.cursor()
    
    new_id = "0" # ID temporário caso a BD falhe

    try:
        # Tenta inserir com o telefone
        cursor.execute("""
            INSERT INTO pedidos_orcamento (nome, email, telefone, servico_id, mensagem, tratado) 
            VALUES (?, ?, ?, ?, ?, 0)
        """, (nome, email, telefone, servico_id, mensagem))
        conn.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        print(f"Aviso: Erro ao gravar na BD (provavelmente falta a coluna telefone): {e}")
        # Se falhar, tenta inserir SEM o telefone para não dar erro ao utilizador
        try:
            cursor.execute("""
                INSERT INTO pedidos_orcamento (nome, email, servico_id, mensagem, tratado) 
                VALUES (?, ?, ?, ?, 0)
            """, (nome, email, servico_id, mensagem))
            conn.commit()
            new_id = cursor.lastrowid
        except:
            pass # Se falhar tudo, avançamos para o email para não perder o contacto

    # Buscar o nome do serviço para o email
    try:
        # Tenta procurar por 'nome'.
        res = conn.execute("SELECT nome FROM servicos WHERE id = ?", (servico_id,)).fetchone()
        servico_nome = res[0] if res else "Serviço Geral"
    except:
        try:
            # Se a coluna não for 'nome', tenta por 'titulo'
            res = conn.execute("SELECT titulo FROM servicos WHERE id = ?", (servico_id,)).fetchone()
            servico_nome = res[0] if res else "Serviço Geral"
        except:
            # Se falhar tudo, define um nome padrão
            servico_nome = "Serviço ID: " + str(servico_id)

    # Fechar a conexão antes de enviar o email
    conn.close()

    # --- ENVIO DE EMAILS (Mesmo que a BD falhe, o email vai!) ---
    corpo_admin = f"<h2>Novo Orçamento</h2><p><b>Nome:</b> {nome}<br><b>Tel:</b> {telefone}<br><b>Email:</b> {email}<br><b>Serviço:</b> {servico_nome}</p><p><b>Mensagem:</b> {mensagem}</p>"
    enviar_email(EMAIL_USER, f"ORÇAMENTO #{new_id} - {nome}", corpo_admin)

    corpo_cliente = f"<h2>Olá {nome}</h2><p>Recebemos o seu pedido para {servico_nome}. Entraremos em contacto brevemente.</p>"
    enviar_email(email, "Visreci - Recebemos o seu pedido", corpo_cliente)

    flash("Pedido enviado com sucesso!", "success")
    return redirect(url_for("servicos"))

@app.route("/admin/pedidos")
@login_required
def admin_pedidos():
    estado = request.args.get('estado')
    conn = get_connection()
    query = "SELECT p.*, s.titulo AS servico_nome FROM pedidos_orcamento p LEFT JOIN servicos s ON p.servico_id = s.id"
    params = []
    if estado in ['0', '1']: query += " WHERE p.tratado = ?"; params.append(estado)
    pedidos = conn.execute(query + " ORDER BY p.id DESC", params).fetchall()
    conn.close()
    return render_template("admin_pedidos.html", pedidos=pedidos, filtro_atual=estado)

@app.route("/admin/pedidos/<int:pedido_id>/tratar")
@login_required
def admin_pedido_tratar(pedido_id):
    conn = get_connection()
    conn.execute("UPDATE pedidos_orcamento SET tratado = 1 WHERE id = ?", (pedido_id,))
    conn.commit()
    log_action("UPDATE", "PEDIDO", pedido_id, "Pedido marcado como tratado")
    conn.close()
    flash("Pedido tratado.", "success")
    return redirect(url_for("admin_pedidos"))

@app.route("/admin/pedidos/exportar")
@login_required
def exportar_pedidos():
    conn = get_connection()
    df = pd.read_sql_query("SELECT p.created_at, p.nome, p.email, s.titulo, p.mensagem FROM pedidos_orcamento p LEFT JOIN servicos s ON p.servico_id = s.id", conn)
    conn.close()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False)
    output.seek(0)
    log_action("EXPORT", "SISTEMA", details="Exportação Excel de Pedidos")
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="pedidos.xlsx")

@app.route("/api/stats/servicos_por_dia")
@login_required
def stats_servicos_por_dia():
    conn = get_connection()
    rows = conn.execute("SELECT substr(COALESCE(created_at, datetime('now')), 1, 10) as dia, COUNT(*) as total FROM servicos GROUP BY dia ORDER BY dia ASC LIMIT 30").fetchall()
    conn.close()
    return jsonify({"labels": [r["dia"] for r in rows], "data": [r["total"] for r in rows]})


# Dicionário de interface - Podes adicionar aqui todas as palavras fixas do site
TRANSLATIONS = {
    'pt': {
        'inicio': 'Início', 'sobre': 'Sobre', 'servicos': 'Serviços', 
        'contactos': 'Contactos', 'equipa': 'Equipa', 'logs': 'Logs',
        'btn_guardar': 'Guardar', 'btn_cancelar': 'Cancelar', 
        'footer_rights': 'Todos os direitos reservados', 'msg_orcamento': 'Pedir Orçamento'
    },
    'en': {
        'inicio': 'Home', 'sobre': 'About', 'servicos': 'Services', 
        'contactos': 'Contacts', 'equipa': 'Team', 'logs': 'Logs',
        'btn_guardar': 'Save', 'btn_cancelar': 'Cancel', 
        'footer_rights': 'All rights reserved', 'msg_orcamento': 'Request Quote'
    }
}

@app.context_processor
def inject_translations():
    # Se não houver língua na sessão, o padrão é 'pt'
    lang = session.get('lang', 'pt')
    return {
        'lang': lang,
        't': TRANSLATIONS.get(lang, TRANSLATIONS['pt'])
    }

@app.route("/admin/logs/limpar", methods=["POST"])
def admin_logs_limpar():
    if "user_id" not in session: 
        return redirect(url_for("login"))
    
    try:
        conn = get_connection()
        conn.execute("DELETE FROM logs")
        conn.commit()
        conn.close()
        
        # Criamos um log novo para dizer que foi limpo
        log_action("DELETE", "SISTEMA", details="O histórico de logs foi limpo.")
        
        flash("Histórico de logs removido com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao limpar: {e}", "error")
        
    return redirect(url_for("admin_logs"))

@app.route("/reclamar", methods=["GET", "POST"])
def reclamar():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        assunto = request.form.get("assunto")
        mensagem = request.form.get("mensagem")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO reclamacoes (nome, email, assunto, mensagem) VALUES (?, ?, ?, ?)",
        (nome, email, assunto, mensagem))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # REGISTAR NAS LOGS
        log_action("CREATE", "RECLAMACAO", new_id, f"Nova reclamação de: {email} sobre: {assunto}")

        # --- ENVIO DE EMAILS AUTOMÁTICOS ---
        
        # 1. Email para o ADMINISTRADOR (Alerta de nova queixa)
        corpo_admin = f"""
        <div style="font-family: Arial, sans-serif; border: 1px solid #ffc107; padding: 20px; border-radius: 10px;">
            <h2 style="color: #ffc107;">⚠️ Nova Reclamação Recebida - Visreci</h2>
            <p><b>ID da Reclamação:</b> #{new_id}</p>
            <p><b>Cliente:</b> {nome}</p>
            <p><b>Email:</b> {email}</p>
            <p><b>Assunto:</b> {assunto}</p>
            <p><b>Mensagem:</b></p>
            <blockquote style="background: #f9f9f9; padding: 10px; border-left: 5px solid #ccc;">{mensagem}</blockquote>
            <hr>
            <p>Acede ao Painel de Gestão para responder a este cliente.</p>
        </div>
        """
        enviar_email(EMAIL_USER, f"ALERTA: Nova Reclamação #{new_id}", corpo_admin)

        # 2. Email para o CLIENTE (Confirmação de receção)
        corpo_cliente = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #198754;">Recebemos a sua mensagem, {nome}!</h2>
            <p>Confirmamos que a sua reclamação sobre <b>"{assunto}"</b> foi registada com sucesso no nosso sistema sob o número <b>#{new_id}</b>.</p>
            <p>A equipa técnica da <b>Visreci</b> irá analisar o seu caso com a maior brevidade possível.</p>
            <br>
            <p>Obrigado pela sua paciência.</p>
            <p><i>Atentamente,</i><br><b>Equipa de Suporte Visreci</b></p>
        </div>
        """
        enviar_email(email, f"Visreci - Confirmação de Reclamação #{new_id}", corpo_cliente)

        flash("Reclamação enviada. Verifique o seu email para a confirmação.", "success")
        return redirect(url_for("index"))
    
    return render_template("reclamar.html")

@app.route("/aceitar-cookies")
def aceitar_cookies():
    # Redireciona para a página anterior ou para a home
    res = make_response(redirect(request.referrer or url_for('index')))
    # Define a cookie 'cookies_aceites' como 'true' por 30 dias
    res.set_cookie('cookies_aceites', 'true', max_age=60*60*24*30)
    return res

@app.route("/admin/reclamacoes/<int:id>/responder_cliente", methods=["GET", "POST"])
@login_required
def responder_reclamacao(id):
    conn = get_connection()
    reclamacao = conn.execute("SELECT * FROM reclamacoes WHERE id = ?", (id,)).fetchone()
    
    if request.method == "POST":
        mensagem_resposta = request.form.get("resposta")
        email_cliente = reclamacao['email']
        nome_cliente = reclamacao['nome']
        assunto_original = reclamacao['assunto']

        # 1. Enviar o Email de Resposta
        corpo_email = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #ffc107; border-radius: 10px;">
            <h2 style="color: #ffc107;">Resposta à sua Reclamação - Visreci</h2>
            <p>Olá <b>{nome_cliente}</b>,</p>
            <p>Em seguimento à sua mensagem sobre "<b>{assunto_original}</b>", a nossa equipa tem a seguinte resposta:</p>
            <div style="background: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                {mensagem_resposta}
            </div>
            <p>Esperamos ter esclarecido a sua questão. Estamos à disposição para qualquer dúvida adicional.</p>
            <hr>
            <p style="font-size: 0.8rem; color: #777;">Este é um email automático, por favor não responda diretamente.</p>
        </div>
        """
        
        if enviar_email(email_cliente, f"RE: {assunto_original} - Visreci", corpo_email):
            # 2. Atualizar o estado na Base de Dados para 'Resolvida'
            conn.execute("UPDATE reclamacoes SET estado = 'Resolvida' WHERE id = ?", (id,))
            conn.commit()
            
            log_action("UPDATE", "RECLAMACAO", id, f"Resposta enviada para {email_cliente}")
            flash("Resposta enviada com sucesso e reclamação encerrada!", "success")
        else:
            flash("Erro ao enviar o email. Verifique as configurações.", "danger")
            
        conn.close()
        return redirect(url_for("admin_reclamacoes"))

    conn.close()
    return render_template("admin_responder_reclamacao.html", r=reclamacao)

@app.route("/admin/orcamentos/<int:id>/responder", methods=["GET", "POST"])
@login_required
def responder_orcamento(id):
    conn = get_connection()
    pedido = conn.execute("""
        SELECT p.*, s.titulo as servico_nome 
        FROM pedidos_orcamento p 
        LEFT JOIN servicos s ON p.servico_id = s.id 
        WHERE p.id = ?
    """, (id,)).fetchone()
    
    if not pedido:
        conn.close()
        flash("Pedido não encontrado.", "danger")
        return redirect(url_for("admin_pedidos"))

    if request.method == "POST":
        mensagem_proposta = request.form.get("proposta")
        valor_estimado = request.form.get("valor")
        email_cliente = pedido['email']
        nome_cliente = pedido['nome']
        servico = pedido['servico_nome'] if pedido['servico_nome'] else "Serviço Geral"

        # --- EMAIL UNIFORMIZADO (AMARELO VISRECI) ---
        corpo_email = f"""
        <div style="font-family: Arial, sans-serif; padding: 25px; border: 2px solid #ffc107; border-radius: 10px;">
            <h2 style="color: #ffc107; margin-bottom: 20px;">💼 Proposta de Orçamento - Visreci</h2>
            <p>Estimado(a) <b>{nome_cliente}</b>,</p>
            <p>Agradecemos o seu contacto para o serviço de <b>{servico}</b>.</p>
            <p>Abaixo apresentamos a nossa proposta detalhada:</p>
            
            <div style="background: #fffdf5; padding: 20px; border-left: 5px solid #ffc107; border-radius: 5px; margin: 20px 0; color: #333;">
                <p style="white-space: pre-wrap; margin: 0;">{mensagem_proposta}</p>
                {f'<div style="margin-top: 15px; font-size: 1.1rem;"><b>Investimento Estimado:</b> <span style="color: #856404; font-weight: bold;">{valor_estimado}€</span></div>' if valor_estimado else ''}
            </div>

            <p>Ficamos a aguardar o seu feedback para procedermos com o agendamento.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 0.85rem; color: #777;"><b>Visreci - Viseu</b><br>Sustentabilidade em primeiro lugar.</p>
        </div>
        """
        
        if enviar_email(email_cliente, f"Proposta Visreci: {servico} (Ref #{id})", corpo_email):
            conn.execute("UPDATE pedidos_orcamento SET tratado = 1 WHERE id = ?", (id,))
            conn.commit()
            log_action("UPDATE", "ORÇAMENTO", id, f"Proposta enviada para {email_cliente}")
            flash("Proposta enviada com sucesso!", "success")
        else:
            flash("Erro ao enviar email.", "danger")
            
        conn.close()
        return redirect(url_for("admin_pedidos"))

    conn.close()
    return render_template("admin_responder_orcamento.html", p=pedido)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)