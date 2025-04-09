import os
import re
import sys
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client
from dotenv import load_dotenv
import locale

locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()

# Configuração do Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URI', 
    'postgresql://postgres:1234@localhost/brisas?client_encoding=utf8'
)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '1234')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicialização de extensões
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configuração Twilio
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)
TWILIO_PHONE = os.getenv('TWILIO_PHONE')

# Modelos do Banco de Dados
class Reclamacao(db.Model):
    __tablename__ = 'reclamacoes'
    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    torre = db.Column(db.String(10), nullable=False)
    apartamento = db.Column(db.String(10), nullable=False)
    reclamacao = db.Column(db.Text, nullable=False)
    foto = db.Column(db.String(100))
    protocolo = db.Column(db.String(20), unique=True, nullable=False)
    resposta = db.Column(db.Text)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='admin')

# Configuração do Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Funções auxiliares
def gerar_protocolo():
    now = datetime.now()
    return f"BRB{now.strftime('%Y%m%d%H%M%S')}"

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def enviar_resposta_email(destinatario, protocolo, resposta):
    smtp_server = os.getenv('SMTP_SERVER')
    port = int(os.getenv('SMTP_PORT', 587))
    sender_email = os.getenv('SMTP_USER')
    password = os.getenv('SMTP_PASSWORD')

    message = MIMEText(f"""Sua reclamação (Protocolo {protocolo}) teve uma atualização:
    
    Resposta do Condomínio:
    {resposta}""")
    
    message['Subject'] = f'Resposta à Reclamação {protocolo} - Brisas Bosque Itirapina'
    message['From'] = sender_email
    message['To'] = destinatario

    try:
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, destinatario, message.as_string())
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

def enviar_whatsapp_resposta(numero, protocolo, resposta):
    try:
        mensagem = f"""*Resposta à sua reclamação ({protocolo})*
        
        {resposta}
        
        _Condomínio Brisas Bosque Itirapina_"""
        
        twilio_client.messages.create(
            body=mensagem,
            from_=f'whatsapp:{TWILIO_PHONE}',
            to=f'whatsapp:+55{numero.translate(str.maketrans("", "", " ()-"))}'
        )
        return True
    except Exception as e:
        print(f"Erro ao enviar WhatsApp: {e}")
        return False

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validar_telefone(numero):
    padrao = re.compile(r'^\(\d{2}\) 9\d{4}-\d{4}$')
    return bool(padrao.match(numero))

def enviar_email(destinatario, protocolo):
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.seuservidor.com')
    port = int(os.getenv('SMTP_PORT', 587))
    sender_email = os.getenv('SMTP_USER', 'condominio@brisas.com')
    password = os.getenv('SMTP_PASSWORD')

    message = MIMEText(f"""Sua reclamação foi registrada com sucesso!
    Número de Protocolo: {protocolo}
    Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}""")
    
    message['Subject'] = 'Protocolo de Reclamação - Condomínio Brisas Bosque'
    message['From'] = sender_email
    message['To'] = destinatario

    try:
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, destinatario, message.as_string())
    except Exception as e:
        print(f"Erro ao enviar email: {e}")

# Rotas
@app.route('/', methods=['GET', 'POST'])
def formulario():
    if request.method == 'POST':
        telefone = request.form['telefone']
        if not validar_telefone(telefone):
            return render_template('formulario.html', 
                error="Telefone inválido. Formato esperado: (XX) 9XXXX-XXXX")
        
        foto = None
        if 'foto' in request.files:
            file = request.files['foto']
            if file.filename != '':
                if not allowed_file(file.filename):
                    return render_template('formulario.html',
                        error="Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF")
                
                if file.content_length > app.config['MAX_CONTENT_LENGTH']:
                    return render_template('formulario.html',
                        error="Arquivo muito grande. Tamanho máximo: 16MB")

                protocolo = gerar_protocolo()
                filename = secure_filename(f"{protocolo}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                foto = filename

        protocolo = gerar_protocolo()
        nova_reclamacao = Reclamacao(
            data_hora=datetime.now(),
            nome=request.form['nome'],
            email=request.form['email'],
            telefone=telefone,
            torre=request.form['torre'],
            apartamento=request.form['apartamento'],
            reclamacao=request.form['reclamacao'],
            foto=foto,
            protocolo=protocolo
        )

        db.session.add(nova_reclamacao)
        db.session.commit()

        enviar_email(request.form['email'], protocolo)
        
        try:
            mensagem = f"""Sua reclamação foi registrada!
            Protocolo: {protocolo}
            Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
            
            twilio_client.messages.create(
                body=mensagem,
                from_=f'whatsapp:{TWILIO_PHONE}',
                to=f'whatsapp:+55{telefone.translate(str.maketrans("", "", " ()-"))}'
            )
        except Exception as e:
            print(f"Erro ao enviar WhatsApp: {e}")

        return redirect(url_for('confirmacao', protocolo=protocolo))
    
    return render_template('formulario.html')

@app.route('/confirmacao/<protocolo>')
def confirmacao(protocolo):
    return render_template('confirmacao.html', protocolo=protocolo)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('admin'))
        return render_template('login.html', error="Credenciais inválidas")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin():
    search_term = request.args.get('search')
    search_type = request.args.get('type', 'protocolo')
    
    query = Reclamacao.query
    
    if search_term:
        if search_type == 'protocolo':
            query = query.filter(Reclamacao.protocolo.contains(search_term))
        elif search_type == 'nome':
            query = query.filter(Reclamacao.nome.ilike(f'%{search_term}%'))
        elif search_type == 'data':
            try:
                data = datetime.strptime(search_term, '%d/%m/%Y')
                query = query.filter(db.func.date(Reclamacao.data_hora) == data.date())
            except ValueError:
                pass
    
    reclamacoes = query.order_by(Reclamacao.data_hora.desc()).all()
    return render_template('admin.html', reclamacoes=reclamacoes)

@app.route('/responder/<int:id>', methods=['POST'])
@login_required
def responder(id):
    reclamacao = Reclamacao.query.get_or_404(id)
    resposta = request.form['resposta']
    metodos = request.form.getlist('metodo')
    
    reclamacao.resposta = resposta
    db.session.commit()
    
    email_enviado = False
    whatsapp_enviado = False
    
    if 'email' in metodos:
        email_enviado = enviar_resposta_email(
            reclamacao.email,
            reclamacao.protocolo,
            resposta
        )
    
    if 'whatsapp' in metodos:
        whatsapp_enviado = enviar_whatsapp_resposta(
            reclamacao.telefone,
            reclamacao.protocolo,
            resposta
        )
    
    # Adicione lógica de feedback se necessário
    return redirect(url_for('admin'))

# Inicialização
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='senha_segura', role='admin')
            db.session.add(admin)
            db.session.commit()
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True')