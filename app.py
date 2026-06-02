from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, make_response
import sqlite3
import os
import io
import math
import pandas as pd
from uuid import uuid4
from werkzeug.utils import secure_filename
from flask import send_file
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps

# Configurações do teu email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "visreciteste@gmail.com"
EMAIL_PASS = "cugr blil vges lvxh"

from email.mime.image import MIMEImage

def enviar_email(destinatario, assunto, corpo, imagem_embed=None):
    try:
        # Usamos 'related' para permitir que imagens embutidas (inline) funcionem corretamente
        msg = MIMEMultipart('related')
        msg['From'] = EMAIL_USER
        msg['To'] = destinatario
        msg['Subject'] = assunto

        # Criamos a parte alternativa para o corpo do texto em HTML
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        msg_alternative.attach(MIMEText(corpo, 'html'))

        # Se for passado um caminho de imagem e o ficheiro existir no disco
        if imagem_embed and os.path.exists(imagem_embed):
            with open(imagem_embed, 'rb') as f:
                img_data = f.read()
            img = MIMEImage(img_data)
            
            # Definimos o Content-ID que vai ser chamado no HTML através de src="cid:logo_visreci"
            img.add_header('Content-ID', '<logo_visreci>')
            img.add_header('Content-Disposition', 'inline', filename=os.path.basename(imagem_embed))
            msg.attach(img)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = "altera-esta-secret-key"

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

def get_connection():
    conn = sqlite3.connect("app.db", timeout=30) 
    conn.row_factory = sqlite3.Row
    return conn

def log_action(action, entity, entity_id=None, details=None):
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trabalhadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'admin'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            descricao TEXT,
            imagem TEXT,
            created_at DATETIME DEFAULT (datetime('now', 'localtime'))
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos_orcamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT,
            telefone TEXT,
            mensagem TEXT,
            servico_id INTEGER,
            tratado INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT (datetime('now', 'localtime'))
        )
    """)

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

import base64

@app.route("/contactos", methods=["GET", "POST"])
def contactos():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        assunto = request.form.get("assunto")
        mensagem = request.form.get("mensagem")

        # Grava o contacto na base de dados local
        conn = get_connection()
        conn.execute("INSERT INTO contactos (nome, email, assunto, mensagem) VALUES (?, ?, ?, ?)",
                     (nome, email, assunto, mensagem))
        conn.commit()
        conn.close()

        # 1. E-MAIL QUE TU (ADMINISTRADOR) RECEBES
        corpo_admin = f"<h2>Novo Contacto de {nome}</h2><p>Assunto: {assunto}</p><p>Mensagem: {mensagem}</p>"
        enviar_email(EMAIL_USER, f"CONTACTO: {assunto}", corpo_admin)

        # 2. CONVERSÃO DO LOGO PARA BASE64 (Garante que a imagem carrega sempre)
        img_base64 = ""
        caminho_real_logo = os.path.join(app.root_path, "static", "IMG", "LogoLetra.png")
        try:
            with open(caminho_real_logo, "rb") as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Erro ao ler imagem nos contactos para Base64: {e}")

        if img_base64:
            tag_logo = f'<img src="data:image/png;base64,{img_base64}" alt="VISRECI" style="max-height: 45px; width: auto; display: inline-block; margin-bottom: 8px;">'
        else:
            tag_logo = '<h1 style="color: #ffffff; margin: 0; font-size: 1.6rem; font-weight: 700; letter-spacing: 1px;">VISRECI</h1>'

        # 3. NOVO E-MAIL AUTOMÁTICO DE CONFIRMAÇÃO PARA O CLIENTE
        corpo_cliente = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background-color: #1a1a1a; padding: 25px 30px; text-align: center; border-bottom: 4px solid #ffc107;">
                {tag_logo}
                <p style="color: #ffc107; margin: 0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600; letter-spacing: 2px;">Reciclagem e Equipamentos Industriais</p>
            </div>
            
            <div style="padding: 35px 25px; background-color: #ffffff; color: #333333; line-height: 1.6;">
                <h2 style="color: #1a1a1a; font-size: 1.3rem; margin-top: 0; margin-bottom: 15px;">Olá {nome},</h2>
                <p style="font-size: 1rem; margin-bottom: 25px;">Agradecemos o seu contacto através da nossa plataforma. Confirmamos que recebemos a sua mensagem com sucesso.</p>
                
                <div style="background-color: #f9f9f9; border-left: 4px solid #ffc107; padding: 20px; border-radius: 0 8px 8px 0; margin-bottom: 30px;">
                    <h4 style="margin: 0 0 5px 0; color: #777777; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;">Assunto do seu contacto:</h4>
                    <p style="margin: 0; color: #1a1a1a; font-size: 1.1rem; font-weight: 700;">{assunto}</p>
                </div>
                
                <p style="font-size: 0.95rem; margin-bottom: 0;">A nossa equipa comercial vai analisar a sua solicitação e entraremos em contacto consigo o mais brevemente possível.</p>
            </div>
            
            <div style="background-color: #f4f4f4; padding: 20px; text-align: center; border-top: 1px solid #eeeeee; font-size: 0.8rem; color: #777777;">
                <p style="margin: 0 0 5px 0; font-weight: 600; color: #444444;">VISRECI, Lda.</p>
                <p style="margin: 0;">Mensagem automática de confirmação de receção. Por favor, não responda a este e-mail.</p>
            </div>
        </div>
        """
        # Envia a resposta automática ao e-mail de quem preencheu o formulário
        enviar_email(email, "Visreci - Recebemos a sua mensagem", corpo_cliente)

        flash("Mensagem enviada com sucesso!", "success")
        return redirect(url_for("contactos"))
        
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
    total_servicos = conn.execute("SELECT COUNT(*) FROM servicos").fetchone()[0]
    total_trabalhadores = conn.execute("SELECT COUNT(*) FROM trabalhadores").fetchone()[0]
    total_equipa = conn.execute("SELECT COUNT(*) FROM equipa").fetchone()[0]
    
    pendentes = conn.execute("SELECT COUNT(*) FROM pedidos_orcamento WHERE tratado = 0").fetchone()[0]
    dp_tratados = conn.execute("SELECT COUNT(*) FROM pedidos_orcamento WHERE tratado = 1").fetchone()[0]
    total_pedidos = pendentes + dp_tratados

    stats_query = """
        SELECT strftime('%m', created_at) as mes, COUNT(*) as total 
        FROM pedidos_orcamento 
        GROUP BY mes 
        ORDER BY mes ASC 
        LIMIT 6
    """
    stats_rows = conn.execute(stats_query).fetchall()
    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    labels_grafico = [meses_nomes[int(r['mes'])-1] for r in stats_rows] if stats_rows else ["Sem dados"]
    dados_grafico = [r['total'] for r in stats_rows] if stats_rows else [0]
    conn.close()
    
    return render_template("dashboard.html", 
                        user_name=session.get("user_name"),
                        total_servicos=total_servicos,
                        total_trabalhadores=total_trabalhadores,
                        total_equipa=total_equipa,
                        pendentes=pendentes,
                        tratados=dp_tratados,
                        total_pedidos=total_pedidos,
                        labels_grafico=labels_grafico,
                        dados_grafico=dados_grafico)

# --- GESTÃO COM PAGINAÇÃO ---

@app.route("/admin/servicos")
@login_required
def admin_servicos():
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_connection()
    servicos = conn.execute("SELECT * FROM servicos ORDER BY id ASC LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM servicos").fetchone()[0]
    conn.close()

    total_pages = max(1, math.ceil(total / per_page))
    return render_template("admin_servicos.html", servicos=servicos, page=page, total_pages=total_pages)

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

@app.route("/admin/equipa")
@login_required
def admin_equipa():
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_connection()
    membros = conn.execute("SELECT * FROM equipa ORDER BY id ASC LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM equipa").fetchone()[0]
    conn.close()

    total_pages = max(1, math.ceil(total / per_page))
    return render_template("admin_equipa.html", membros=membros, page=page, total_pages=total_pages)

@app.route("/admin/equipa/novo", methods=["GET", "POST"])
@login_required
def admin_equipa_novo():
    if request.method == "POST":
        name, cargo, desc = request.form.get("nome"), request.form.get("cargo"), request.form.get("descricao")
        foto = save_upload(request.files.get("foto"), "equipa")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO equipa (nome, cargo, descricao, foto, ativo) VALUES (?, ?, ?, ?, 1)", (name, cargo, desc, foto))
        conn.commit()
        new_id = cursor.lastrowid
        log_action("CREATE", "EQUIPA", new_id, f"Adicionou {name}")
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
        name = request.form.get("nome")
        cargo = request.form.get("cargo")
        desc = request.form.get("descricao")
        ativo = 1 if request.form.get("ativo") == "1" else 0
        
        nova_foto = request.files.get("foto")
        if nova_foto and nova_foto.filename != '':
            foto_nome = save_upload(nova_foto, "equipa")
            conn.execute("UPDATE equipa SET nome=?, cargo=?, descricao=?, foto=?, ativo=? WHERE id=?", 
                        (name, cargo, desc, foto_nome, ativo, membro_id))
        else:
            conn.execute("UPDATE equipa SET nome=?, cargo=?, descricao=?, ativo=? WHERE id=?", 
                        (name, cargo, desc, ativo, membro_id))
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

import base64

@app.route("/pedir_orcamento", methods=["POST"])
def pedir_orcamento():
    nome = request.form.get("nome")
    email = request.form.get("email")
    telefone = request.form.get("telefone")
    servico_id = request.form.get("servico_id")
    mensagem = request.form.get("mensagem")

    conn = get_connection()
    cursor = conn.cursor()
    new_id = "0"

    # --- CORREÇÃO DA GRAVAÇÃO NA BASE DE DADOS (mensagem em vez de message) ---
    try:
        cursor.execute("""
            INSERT INTO pedidos_orcamento (nome, email, telefone, servico_id, mensagem, tratado) 
            VALUES (?, ?, ?, ?, ?, 0)
        """, (nome, email, telefone, servico_id, mensagem))
        conn.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        print(f"Erro na primeira tentativa de gravação: {e}")
        try:
            cursor.execute("""
                INSERT INTO pedidos_orcamento (nome, email, servico_id, mensagem, tratado) 
                VALUES (?, ?, ?, ?, 0)
            """, (nome, email, servico_id, mensagem))
            conn.commit()
            new_id = cursor.lastrowid
        except Exception as e2:
            print(f"Erro crítico ao gravar orçamento: {e2}")

    try:
        res = conn.execute("SELECT titulo FROM servicos WHERE id = ?", (servico_id,)).fetchone()
        servico_nome = res[0] if res else "Serviço Geral"
    except:
        servico_nome = "Serviço ID: " + str(servico_id)

    conn.close()

    # --- 1. Email do Administrador ---
    corpo_admin = f"<h2>Novo Orçamento</h2><p><b>Nome:</b> {nome}<br><b>Tel:</b> {telefone}<br><b>Email:</b> {email}<br><b>Serviço:</b> {servico_nome}</p><p><b>Mensagem:</b> {mensagem}</p>"
    enviar_email(EMAIL_USER, f"ORÇAMENTO #{new_id} - {nome}", corpo_admin)

    # --- 2. CONVERSÃO DO LOGO PARA BASE64 ---
    img_base64 = ""
    caminho_real_logo = os.path.join(app.root_path, "static", "IMG", "LogoLetra.png")
    
    try:
        with open(caminho_real_logo, "rb") as image_file:
            img_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Erro ao verificar imagem para Base64: {e}")

    if img_base64:
        tag_logo = f'<img src="data:image/png;base64,{img_base64}" alt="VISRECI" style="max-height: 45px; width: auto; display: inline-block; margin-bottom: 8px;">'
    else:
        tag_logo = '<h1 style="color: #ffffff; margin: 0; font-size: 1.6rem; font-weight: 700; letter-spacing: 1px;">VISRECI</h1>'

    # --- 3. EMAIL CORPORATIVO DO CLIENTE ---
    corpo_cliente = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <div style="background-color: #1a1a1a; padding: 25px 30px; text-align: center; border-bottom: 4px solid #ffc107;">
            {tag_logo}
            <p style="color: #ffc107; margin: 0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600; letter-spacing: 2px;">Reciclagem e Equipamentos Industriais</p>
        </div>
        
        <div style="padding: 35px 25px; background-color: #ffffff; color: #333333; line-height: 1.6;">
            <h2 style="color: #1a1a1a; font-size: 1.3rem; margin-top: 0; margin-bottom: 15px;">Olá {nome},</h2>
            <p style="font-size: 1rem; margin-bottom: 25px;">Confirmamos que recebemos com sucesso o seu pedido de orçamento. A nossa equipa técnica já está a analisar as especificações fornecidas.</p>
            
            <div style="background-color: #f9f9f9; border-left: 4px solid #ffc107; padding: 20px; border-radius: 0 8px 8px 0; margin-bottom: 30px;">
                <h4 style="margin: 0 0 5px 0; color: #777777; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;">Equipamento / Serviço Selecionado:</h4>
                <p style="margin: 0; color: #1a1a1a; font-size: 1.1rem; font-weight: 700;">{servico_nome}</p>
            </div>
            
            <p style="font-size: 0.95rem; margin-bottom: 0;">Entraremos em contacto consigo muito brevemente com uma proposta detalhada ou para esclarecer eventuais detalhes técnicos.</p>
        </div>
        
        <div style="background-color: #f4f4f4; padding: 20px; text-align: center; border-top: 1px solid #eeeeee; font-size: 0.8rem; color: #777777;">
            <p style="margin: 0 0 5px 0; font-weight: 600; color: #444444;">VISRECI, Lda.</p>
            <p style="margin: 0;">Mensagem automática de confirmação de receção. Por favor, não responda a este e-mail.</p>
        </div>
    </div>
    """
    
    enviar_email(email, "Visreci - Recebemos o seu pedido", corpo_cliente)

    flash("Pedido enviado com sucesso!", "success")
    return redirect(url_for("servicos"))

@app.route("/admin/pedidos")
@login_required
def admin_pedidos():
    estado = request.args.get('estado')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_connection()
    count_query = "SELECT COUNT(*) FROM pedidos_orcamento"
    data_query = "SELECT p.*, s.titulo AS servico_nome FROM pedidos_orcamento p LEFT JOIN servicos s ON p.servico_id = s.id"
    
    params = []
    if estado in ['0', '1']:
        count_query += " WHERE tratado = ?"
        data_query += " WHERE p.tratado = ?"
        params.append(estado)
        
    total = conn.execute(count_query, params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))
    
    data_query += " ORDER BY p.id DESC LIMIT ? OFFSET ?"
    pedidos = conn.execute(data_query, params + [per_page, offset]).fetchall()
    conn.close()
    
    return render_template("admin_pedidos.html", pedidos=pedidos, filtro_atual=estado, page=page, total_pages=total_pages)

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
    lang = session.get('lang', 'pt')
    return { 'lang': lang, 't': TRANSLATIONS.get(lang, TRANSLATIONS['pt']) }

@app.route("/admin/logs/limpar", methods=["POST"])
def admin_logs_limpar():
    if "user_id" not in session: return redirect(url_for("login"))
    try:
        conn = get_connection()
        conn.execute("DELETE FROM logs")
        conn.commit()
        conn.close()
        log_action("DELETE", "SISTEMA", details="O histórico de logs foi limpo.")
        flash("Histórico de logs removido com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao limpar: {e}", "error")
    return redirect(url_for("admin_logs"))

@app.route("/aceitar-cookies")
def aceitar_cookies():
    res = make_response(redirect(request.referrer or url_for('index')))
    res.set_cookie('cookies_aceites', 'true', max_age=60*60*24*30)
    return res

@app.route("/admin/orcamentos/<int:id>/responder", methods=["GET", "POST"])
@login_required
def responder_orcamento(id):
    conn = get_connection()
    pedido = conn.execute("SELECT p.*, s.titulo as servico_nome FROM pedidos_orcamento p LEFT JOIN servicos s ON p.servico_id = s.id WHERE p.id = ?", (id,)).fetchone()
    
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

        # --- CONVERSÃO DO LOGO PARA BASE64 ---
        img_base64 = ""
        caminho_real_logo = os.path.join(app.root_path, "static", "IMG", "LogoLetra.png")
        try:
            with open(caminho_real_logo, "rb") as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Erro ao ler imagem na proposta para Base64: {e}")

        if img_base64:
            tag_logo = f'<img src="data:image/png;base64,{img_base64}" alt="VISRECI" style="max-height: 45px; width: auto; display: inline-block; margin-bottom: 8px;">'
        else:
            tag_logo = '<h1 style="color: #ffffff; margin: 0; font-size: 1.6rem; font-weight: 700; letter-spacing: 1px;">VISRECI</h1>'

        # --- NOVO TEMPLATE DE E-MAIL DE PROPOSTA PREMIUM (Substitui o da imagem image_c53367.png) ---
        corpo_email = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background-color: #1a1a1a; padding: 25px 30px; text-align: center; border-bottom: 4px solid #ffc107;">
                {tag_logo}
                <p style="color: #ffc107; margin: 0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600; letter-spacing: 2px;">Proposta Comercial</p>
            </div>
            
            <div style="padding: 35px 25px; background-color: #ffffff; color: #333333; line-height: 1.6;">
                <h2 style="color: #1a1a1a; font-size: 1.3rem; margin-top: 0; margin-bottom: 15px;">Estimado(a) {nome_cliente},</h2>
                <p style="font-size: 1rem;">Agradecemos o seu contacto e preferência pela <b>VISRECI</b>. Na sequência do seu pedido para o equipamento/serviço <b>{servico}</b>, elaborámos a seguinte proposta técnica e comercial:</p>
                
                <div style="background-color: #f9f9f9; border-left: 4px solid #ffc107; padding: 20px; border-radius: 4px; margin: 25px 0; color: #222222; white-space: pre-wrap; font-size: 0.95rem;">{mensagem_proposta}</div>
                
                {f'''
                <div style="background-color: #fffdf0; border: 1px dashed #ffc107; padding: 15px 20px; border-radius: 8px; text-align: center; margin-bottom: 25px;">
                    <span style="color: #666666; font-size: 0.85rem; text-transform: uppercase; display: block; margin-bottom: 4px; font-weight: 600; letter-spacing: 0.5px;">Investimento Estimado Global:</span>
                    <span style="color: #1a1a1a; font-size: 1.6rem; font-weight: 800;">{valor_estimado}€</span>
                </div>
                ''' if valor_estimado else ''}
                
                <p style="font-size: 0.95rem; margin-top: 25px; margin-bottom: 0;">Ficamos inteiramente à sua disposição para qualquer esclarecimento técnico ou ajuste necessário.</p>
                <p style="font-size: 0.95rem; margin-top: 10px;">Com os nossos melhores cumprimentos,</p>
            </div>
            
            <div style="background-color: #f4f4f4; padding: 20px; text-align: center; border-top: 1px solid #eeeeee; font-size: 0.8rem; color: #777777;">
                <p style="margin: 0 0 5px 0; font-weight: 600; color: #444444;">VISRECI, Lda.</p>
                <p style="margin: 0;">Equipa Comercial e de Engenharia</p>
            </div>
        </div>
        """
        
        if enviar_email(email_cliente, f"Proposta Visreci: {servico} (Ref #{id})", corpo_email):
            conn.execute("UPDATE pedidos_orcamento SET tratado = 1 WHERE id = ?", (id,))
            conn.commit()
            log_action("UPDATE", "ORÇAMENTO", id, f"Proposta enviada para {email_cliente}")
            flash("Proposta enviada com sucesso!", "success")
        else:
            flash("Erro ao enviar o e-mail da proposta.", "danger")
        conn.close()
        return redirect(url_for("admin_pedidos"))

    conn.close()
    return render_template("admin_responder_orcamento.html", p=pedido)

@app.route("/admin/contactos/<int:id>/responder", methods=["GET", "POST"])
@login_required
def responder_contacto(id):
    conn = get_connection()
    # Assume-se que a tua tabela se chama 'contactos'
    contacto = conn.execute("SELECT * FROM contactos WHERE id = ?", (id,)).fetchone()
    
    if not contacto:
        conn.close()
        flash("Mensagem de contacto não encontrada.", "danger")
        return redirect(url_for("admin_contactos"))

    if request.method == "POST":
        mensagem_resposta = request.form.get("resposta")
        email_cliente = contacto['email']
        nome_cliente = contacto['nome']
        assunto_original = contacto['assunto']

        # --- CONVERSÃO DO LOGO PARA BASE64 ---
        img_base64 = ""
        caminho_real_logo = os.path.join(app.root_path, "static", "IMG", "LogoLetra.png")
        try:
            with open(caminho_real_logo, "rb") as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Erro ao ler imagem na resposta de contacto: {e}")

        if img_base64:
            tag_logo = f'<img src="data:image/png;base64,{img_base64}" alt="VISRECI" style="max-height: 45px; width: auto; display: inline-block; margin-bottom: 8px;">'
        else:
            tag_logo = '<h1 style="color: #ffffff; margin: 0; font-size: 1.6rem; font-weight: 700; letter-spacing: 1px;">VISRECI</h1>'

        # --- TEMPLATE DE E-MAIL DE RESPOSTA PREMIUM ---
        corpo_email = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background-color: #1a1a1a; padding: 25px 30px; text-align: center; border-bottom: 4px solid #ffc107;">
                {tag_logo}
                <p style="color: #ffc107; margin: 0; font-size: 0.85rem; text-transform: uppercase; font-weight: 600; letter-spacing: 2px;">Resposta ao seu Contacto</p>
            </div>
            
            <div style="padding: 35px 25px; background-color: #ffffff; color: #333333; line-height: 1.6;">
                <h2 style="color: #1a1a1a; font-size: 1.3rem; margin-top: 0; margin-bottom: 15px;">Olá {nome_cliente},</h2>
                <p style="font-size: 1rem;">No seguimento da mensagem que nos enviou com o assunto "<b>{assunto_original}</b>", a nossa equipa apresenta a seguinte resposta:</p>
                
                <div style="background-color: #f9f9f9; border-left: 4px solid #ffc107; padding: 20px; border-radius: 4px; margin: 25px 0; color: #222222; white-space: pre-wrap; font-size: 0.95rem;">{mensagem_resposta}</div>
                
                <p style="font-size: 0.95rem; margin-bottom: 0;">Caso necessite de mais alguma informação ou esclarecimento adicional, não hesite em responder a este e-mail.</p>
                <p style="font-size: 0.95rem; margin-top: 15px;">Melhores cumprimentos,</p>
            </div>
            
            <div style="background-color: #f4f4f4; padding: 20px; text-align: center; border-top: 1px solid #eeeeee; font-size: 0.8rem; color: #777777;">
                <p style="margin: 0 0 5px 0; font-weight: 600; color: #444444;">VISRECI, Lda.</p>
                <p style="margin: 0;">Suporte e Apoio ao Cliente</p>
            </div>
        </div>
        """
        
        if enviar_email(email_cliente, f"RE: {assunto_original} - Visreci", corpo_email):
            # Opcional: Se tiveres uma coluna 'tratado' na tabela contactos, podes fazer UPDATE aqui
            flash("Resposta enviada com sucesso!", "success")
        else:
            flash("Erro ao enviar o e-mail de resposta.", "danger")
            
        conn.close()
        return redirect(url_for("admin_contactos"))

    conn.close()
    return render_template("admin_responder_contacto.html", c=contacto)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)