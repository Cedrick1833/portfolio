import os
import json
import sqlite3
import time
import smtplib
import functools
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, g
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'cedrick-portfolio-secret-key-2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
DATABASE = os.path.join(BASE_DIR, 'portfolio.db')

@app.after_request
def add_no_cache(resp):
    """Empêche le cache navigateur sur les ressources qui changent au fil des mises à jour admin."""
    if resp.content_type and 'text/html' in resp.content_type:
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    elif resp.content_type and 'javascript' in resp.content_type:
        resp.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
    elif resp.content_type and 'text/css' in resp.content_type:
        resp.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
    return resp

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
PHOTO_FOLDER = os.path.join(UPLOAD_FOLDER, 'photo')
CERTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'certs')
CV_FOLDER = os.path.join(UPLOAD_FOLDER, 'cv')
CERTIF_FILES_FOLDER = os.path.join(UPLOAD_FOLDER, 'certifs')

for folder in [PHOTO_FOLDER, CERTS_FOLDER, CV_FOLDER, CERTIF_FILES_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ---------- CONFIG ----------

def get_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "admin_email": "",
        "admin_password": "admin",
        "smtp_email": "",
        "smtp_app_password": "",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587
    }

# ---------- SQLITE DATABASE ----------

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'obtenue',
            created_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_read INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS realisations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            image TEXT DEFAULT '',
            code_url TEXT DEFAULT '',
            demo_url TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS formations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            institution TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'en_cours',
            created_at TEXT NOT NULL
        )
    ''')
    cert_cols = [r[1] for r in cursor.execute('PRAGMA table_info(certifications)').fetchall()]
    if 'file_url' not in cert_cols:
        cursor.execute("ALTER TABLE certifications ADD COLUMN file_url TEXT DEFAULT ''")
    if 'file_name' not in cert_cols:
        cursor.execute("ALTER TABLE certifications ADD COLUMN file_name TEXT DEFAULT ''")
    db.commit()
    db.close()

def seed_catalog():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    count = cursor.execute('SELECT COUNT(*) FROM realisations').fetchone()[0]
    if count == 0:
        now = datetime.now().isoformat()
        realisations = [
            ("Plateforme de gestion d'école",
             "Application complète en architecture microservices : élèves, notes, paiements, notifications. 8 services indépendants, orchestrés sur Kubernetes.",
             "/static/img/project-microservices.svg", "", "",
             "Python,Flask,Docker,Kubernetes,PostgreSQL,Redis,RabbitMQ", now),
            ("Pipeline CI/CD sécurisé",
             "Chaîne de déploiement automatisée : tests, scans de vulnérabilités, analyse d'images Docker et déploiement Kubernetes — la sécurité versionnée comme le code.",
             "/static/img/project-cicd.svg", "", "",
             "GitHub Actions,CI/CD,IaC,Security as Code", now),
            ("Durcissement & audit sécurité",
             "Audit d'applications et d'infrastructures : OWASP, authentification JWT, chiffrement, analyse de vulnérabilités et recommandations correctives.",
             "/static/img/project-security.svg", "", "",
             "OWASP,JWT,Chiffrement,Pentest", now),
            ("Infrastructure as Code",
             "Infrastructure Kubernetes entièrement déclarative et versionnée : Terraform, Helm, rolling updates. Le cluster est reproductible à l'identique, sans configuration manuelle.",
             "/static/img/project-iac.svg", "", "",
             "Terraform,Helm,IaC,Kubernetes", now),
            ("Observabilité & Monitoring",
             "Supervision complète de la plateforme : métriques temps réel, dashboards Grafana, alerting automatisé. Un système que l'on ne peut pas observer ne peut pas être amélioré.",
             "/static/img/project-monitoring.svg", "", "",
             "Prometheus,Grafana,Alerting,SLO", now),
            ("API sécurisée & Authentification",
             "Authentification JWT avec tokens de rafraîchissement, OAuth2, contrôle d'accès RBAC, rate limiting et chiffrement TLS. Chaque API est protégée dès sa conception.",
             "/static/img/project-api-auth.svg", "", "",
             "JWT,OAuth2,RBAC,TLS", now),
        ]
        cursor.executemany(
            'INSERT INTO realisations (title, description, image, code_url, demo_url, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            realisations
        )
    fcount = cursor.execute('SELECT COUNT(*) FROM formations').fetchone()[0]
    if fcount == 0:
        formations = [
            ("Master Management of Business Administration",
             "Unicaf University — comprendre les enjeux business et stratégiques de la technologie.",
             "Unicaf University", "en_cours"),
            ("Master Télécoms et sécurité — Spécialisation Cybersécurité",
             "Techniques avancées d'analyse de vulnérabilités, sécurité applicative et réponse aux incidents.",
             "", "en_cours"),
        ]
        for f in formations:
            cursor.execute(
                'INSERT INTO formations (title, description, institution, status, created_at) VALUES (?, ?, ?, ?, ?)',
                (f[0], f[1], f[2], f[3], now)
            )
    db.commit()
    db.close()

def record_upload(category, filename, original_name, url):
    db = get_db()
    db.execute(
        'INSERT INTO uploads (category, filename, original_name, url, created_at) VALUES (?, ?, ?, ?, ?)',
        (category, filename, original_name, url, datetime.now().isoformat())
    )
    db.commit()

def delete_records(category, filename=None):
    db = get_db()
    if filename:
        db.execute('DELETE FROM uploads WHERE category = ? AND filename = ?', (category, filename))
    else:
        db.execute('DELETE FROM uploads WHERE category = ?', (category,))
    db.commit()

def get_uploads(category):
    db = get_db()
    rows = db.execute(
        'SELECT * FROM uploads WHERE category = ? ORDER BY id DESC',
        (category,)
    ).fetchall()
    return [dict(row) for row in rows]

# --- CERTIFICATIONS DB ---

def add_certification(title, description, status):
    db = get_db()
    db.execute(
        'INSERT INTO certifications (title, description, status, created_at) VALUES (?, ?, ?, ?)',
        (title, description, status, datetime.now().isoformat())
    )
    cert_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    db.commit()
    return cert_id

def delete_certification(cert_id):
    db = get_db()
    db.execute('DELETE FROM certifications WHERE id = ?', (cert_id,))
    db.commit()

def get_certifications():
    db = get_db()
    rows = db.execute('SELECT * FROM certifications ORDER BY id DESC').fetchall()
    return [dict(row) for row in rows]

def update_certification(cert_id, title, description, status):
    db = get_db()
    db.execute(
        'UPDATE certifications SET title = ?, description = ?, status = ? WHERE id = ?',
        (title, description, status, cert_id)
    )
    db.commit()

def attach_cert_file(cert_id, filename, url):
    db = get_db()
    db.execute(
        'UPDATE certifications SET file_name = ?, file_url = ? WHERE id = ?',
        (filename, url, cert_id)
    )
    db.commit()

def get_cert_file(cert_id):
    db = get_db()
    row = db.execute('SELECT * FROM certifications WHERE id = ?', (cert_id,)).fetchone()
    if not row:
        return None
    return dict(row)['file_url'] or None

# --- REALISATIONS DB ---

def add_realisation(title, description, image, code_url, demo_url, tags):
    db = get_db()
    db.execute(
        'INSERT INTO realisations (title, description, image, code_url, demo_url, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (title, description, image, code_url, demo_url, tags, datetime.now().isoformat())
    )
    db.commit()

def update_realisation(rel_id, title, description, image, code_url, demo_url, tags):
    db = get_db()
    db.execute(
        'UPDATE realisations SET title = ?, description = ?, image = ?, code_url = ?, demo_url = ?, tags = ? WHERE id = ?',
        (title, description, image, code_url, demo_url, tags, rel_id)
    )
    db.commit()

def delete_realisation(rel_id):
    db = get_db()
    db.execute('DELETE FROM realisations WHERE id = ?', (rel_id,))
    db.commit()

def get_realisations():
    db = get_db()
    rows = db.execute('SELECT * FROM realisations ORDER BY id DESC').fetchall()
    return [dict(row) for row in rows]

# --- FORMATIONS DB ---

def add_formation(title, description, institution, status):
    db = get_db()
    db.execute(
        'INSERT INTO formations (title, description, institution, status, created_at) VALUES (?, ?, ?, ?, ?)',
        (title, description, institution, status, datetime.now().isoformat())
    )
    db.commit()

def update_formation(form_id, title, description, institution, status):
    db = get_db()
    db.execute(
        'UPDATE formations SET title = ?, description = ?, institution = ?, status = ? WHERE id = ?',
        (title, description, institution, status, form_id)
    )
    db.commit()

def delete_formation(form_id):
    db = get_db()
    db.execute('DELETE FROM formations WHERE id = ?', (form_id,))
    db.commit()

def get_formations():
    db = get_db()
    rows = db.execute('SELECT * FROM formations ORDER BY id DESC').fetchall()
    return [dict(row) for row in rows]

# --- MESSAGES DB ---

def save_message(nom, email, message):
    db = get_db()
    db.execute(
        'INSERT INTO messages (nom, email, message, created_at) VALUES (?, ?, ?, ?)',
        (nom, email, message, datetime.now().isoformat())
    )
    db.commit()

def get_messages():
    db = get_db()
    rows = db.execute('SELECT * FROM messages ORDER BY id DESC').fetchall()
    return [dict(row) for row in rows]

def mark_message_read(msg_id):
    db = get_db()
    db.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (msg_id,))
    db.commit()

def delete_message(msg_id):
    db = get_db()
    db.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    db.commit()

# --- EMAIL ---

def send_email(nom, email_visiteur, message):
    config = get_config()
    smtp_email = config.get('smtp_email', '')
    smtp_pass = config.get('smtp_app_password', '')
    smtp_server = config.get('smtp_server', 'smtp.gmail.com')
    smtp_port = config.get('smtp_port', 587)
    admin_email = config.get('admin_email', '')

    if not smtp_email or not smtp_pass:
        print('SMTP non configuré : le message a été sauvegardé mais non envoyé par email.')
        return False, 'SMTP non configuré'

    msg = MIMEMultipart()
    msg['From'] = smtp_email
    msg['To'] = admin_email
    msg['Subject'] = f'Nouveau message de {nom} — Portfolio'
    body = f'''
Nouveau message reçu via le formulaire de contact :

Nom : {nom}
Email : {email_visiteur}

Message :
{message}

---
Envoyé depuis le formulaire de contact du portfolio.
    '''
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_email, smtp_pass)
        server.sendmail(smtp_email, admin_email, msg.as_string())
        server.quit()
        return True, 'OK'
    except smtplib.SMTPAuthenticationError:
        return False, "Authentification SMTP échouée (email ou mot de passe d'application incorrect)."
    except smtplib.SMTPException as e:
        return False, f'Erreur SMTP: {e}'
    except Exception as e:
        return False, f'Erreur envoi email: {e}'

init_db()
seed_catalog()

# ---------- AUTH ----------

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- ROUTES ----------

@app.route('/')
def index():
    cert_db = get_certifications()
    certifications_count = len(cert_db)
    realisations_count = len(get_realisations())
    formations_count = len(get_formations())
    return render_template(
        'index.html',
        formations=get_formations(),
        certifications_count=certifications_count,
        realisations_count=realisations_count,
        formations_count=formations_count,
    )

# --- PUBLIC API ---

@app.route('/api/contact', methods=['POST'])
def api_contact():
    data = request.get_json()
    nom = data.get('nom', '').strip()
    email = data.get('email', '').strip()
    message = data.get('message', '').strip()

    if not nom or not email or not message:
        return jsonify({'error': 'Tous les champs sont requis.'}), 400

    save_message(nom, email, message)
    sent, email_status = send_email(nom, email, message)

    return jsonify({'success': True, 'email_sent': sent, 'email_status': email_status})

@app.route('/api/certs', methods=['GET'])
def get_certs():
    return jsonify([
        {'filename': c['filename'], 'url': c['url'], 'original_name': c.get('original_name', '')}
        for c in get_uploads('cert')
    ])

@app.route('/api/certifications', methods=['GET'])
def get_certifications_api():
    return jsonify(get_certifications())

@app.route('/api/realisations', methods=['GET'])
def get_realisations_api():
    return jsonify(get_realisations())

@app.route('/api/formations', methods=['GET'])
def get_formations_api():
    return jsonify(get_formations())

@app.route('/api/cv', methods=['GET'])
def get_cv():
    cv_list = get_uploads('cv')
    if cv_list:
        c = cv_list[0]
        return jsonify({'filename': c['filename'], 'url': c['url']})
    return jsonify({})

@app.route('/api/photo', methods=['GET'])
def get_photo():
    photo_list = get_uploads('photo')
    if photo_list:
        p = photo_list[0]
        return jsonify({'filename': p['filename'], 'url': p['url']})
    return jsonify({})

# --- ADMIN ROUTES ---

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        config = get_config()
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        config_email = config.get('admin_email', '')
        config_password = config.get('admin_password', 'admin')
        if email == config_email and password == config_password:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Email ou mot de passe incorrect.'
    return render_template('admin_login.html', error=error)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    cv_list = get_uploads('cv')
    cv_info = {}
    if cv_list:
        cv_info = {'filename': cv_list[0]['filename'], 'url': cv_list[0]['url']}

    photo_list = get_uploads('photo')
    photo_info = {}
    if photo_list:
        photo_info = {'filename': photo_list[0]['filename'], 'url': photo_list[0]['url']}

    certifications = get_certifications()
    realisations = get_realisations()
    formations = get_formations()
    messages = get_messages()
    unread_count = sum(1 for m in messages if not m['is_read'])

    config = get_config()

    return render_template('admin.html',
        cv=cv_info, photo=photo_info,
        certifications=certifications,
        realisations=realisations,
        formations=formations,
        messages=messages, unread_count=unread_count,
        smtp_configured=bool(config.get('smtp_email') and config.get('smtp_app_password'))
    )

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# --- ADMIN API ROUTES ---

@app.route('/admin/api/upload/photo', methods=['POST'])
@login_required
def admin_upload_photo():
    if 'photo' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        for f in os.listdir(PHOTO_FOLDER):
            os.remove(os.path.join(PHOTO_FOLDER, f))
        delete_records('photo')
        filename = secure_filename(file.filename)
        file.save(os.path.join(PHOTO_FOLDER, filename))
        url = f'/static/uploads/photo/{filename}'
        record_upload('photo', filename, file.filename, url)
        return jsonify({'filename': filename, 'url': url})

@app.route('/admin/api/upload/cert', methods=['POST'])
@login_required
def admin_upload_cert():
    if 'cert' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['cert']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        filename = f"{int(time.time())}_{filename}"
        file.save(os.path.join(CERTS_FOLDER, filename))
        url = f'/static/uploads/certs/{filename}'
        record_upload('cert', filename, file.filename, url)
        return jsonify({'filename': filename, 'url': url})

@app.route('/admin/api/cert/<filename>', methods=['DELETE'])
@login_required
def admin_delete_cert(filename):
    filepath = os.path.join(CERTS_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        delete_records('cert', filename)
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Not found'}), 404

@app.route('/admin/api/upload/cv', methods=['POST'])
@login_required
def admin_upload_cv():
    if 'cv' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['cv']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        for f in os.listdir(CV_FOLDER):
            os.remove(os.path.join(CV_FOLDER, f))
        delete_records('cv')
        filename = secure_filename(file.filename)
        file.save(os.path.join(CV_FOLDER, filename))
        url = f'/static/uploads/cv/{filename}'
        record_upload('cv', filename, file.filename, url)
        return jsonify({'filename': filename, 'url': url})

@app.route('/admin/api/cv', methods=['DELETE'])
@login_required
def admin_delete_cv():
    if os.path.exists(CV_FOLDER):
        for f in os.listdir(CV_FOLDER):
            os.remove(os.path.join(CV_FOLDER, f))
        delete_records('cv')
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Not found'}), 404

# --- CERTIFICATIONS ---

@app.route('/admin/api/certifications', methods=['POST'])
@login_required
def admin_add_certification():
    status = 'obtenue'
    title = ''
    description = ''
    file = None
    if request.content_type and 'multipart/form-data' in request.content_type:
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        status = request.form.get('status', 'obtenue')
        if 'file' in request.files:
            f = request.files['file']
            if f.filename:
                file = f
    else:
        data = request.get_json()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        status = data.get('status', 'obtenue')
    if not title or not description:
        return jsonify({'error': 'Titre et description requis'}), 400
    if status not in ('obtenue', 'en_cours'):
        status = 'obtenue'
    cert_id = add_certification(title, description, status)
    if file:
        ext = os.path.splitext(file.filename)[1] or '.pdf'
        filename = f"cert_{cert_id}_{int(time.time())}{ext}"
        file.save(os.path.join(CERTIF_FILES_FOLDER, filename))
        url = f'/static/uploads/certifs/{filename}'
        attach_cert_file(cert_id, file.filename, url)
    return jsonify({'success': True})

@app.route('/admin/api/certifications/<int:cert_id>', methods=['PUT', 'DELETE'])
@login_required
def admin_modify_certification(cert_id):
    if request.method == 'DELETE':
        file_url = get_cert_file(cert_id)
        if file_url:
            fname = os.path.basename(file_url)
            fpath = os.path.join(CERTIF_FILES_FOLDER, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
        delete_certification(cert_id)
        return jsonify({'status': 'deleted'})

    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    status = data.get('status', 'obtenue')
    if not title or not description:
        return jsonify({'error': 'Titre et description requis'}), 400
    if status not in ('obtenue', 'en_cours'):
        status = 'obtenue'
    update_certification(cert_id, title, description, status)
    return jsonify({'success': True})

@app.route('/admin/api/certifications/<int:cert_id>/file', methods=['POST', 'DELETE'])
@login_required
def admin_certification_file(cert_id):
    if request.method == 'DELETE':
        file_url = get_cert_file(cert_id)
        if not file_url:
            return jsonify({'status': 'deleted'})
        fname = os.path.basename(file_url)
        fpath = os.path.join(CERTIF_FILES_FOLDER, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
        attach_cert_file(cert_id, '', '')
        return jsonify({'status': 'deleted'})

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    file_url = get_cert_file(cert_id)
    if file_url:
        old = os.path.basename(file_url)
        old_path = os.path.join(CERTIF_FILES_FOLDER, old)
        if os.path.exists(old_path):
            os.remove(old_path)
    ext = os.path.splitext(file.filename)[1] or '.pdf'
    filename = f"cert_{cert_id}_{int(time.time())}{ext}"
    file.save(os.path.join(CERTIF_FILES_FOLDER, filename))
    url = f'/static/uploads/certifs/{filename}'
    attach_cert_file(cert_id, file.filename, url)
    return jsonify({'filename': filename, 'url': url})

# --- REALISATIONS ---

@app.route('/admin/api/realisations', methods=['POST'])
@login_required
def admin_add_realisation():
    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    image = data.get('image', '').strip()
    code_url = data.get('code_url', '').strip()
    demo_url = data.get('demo_url', '').strip()
    tags = data.get('tags', '').strip()
    if not title or not description:
        return jsonify({'error': 'Titre et description requis'}), 400
    add_realisation(title, description, image, code_url, demo_url, tags)
    return jsonify({'success': True})

@app.route('/admin/api/realisations/<int:rel_id>', methods=['PUT', 'DELETE'])
@login_required
def admin_modify_realisation(rel_id):
    if request.method == 'DELETE':
        delete_realisation(rel_id)
        return jsonify({'status': 'deleted'})

    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    image = data.get('image', '').strip()
    code_url = data.get('code_url', '').strip()
    demo_url = data.get('demo_url', '').strip()
    tags = data.get('tags', '').strip()
    if not title or not description:
        return jsonify({'error': 'Titre et description requis'}), 400
    update_realisation(rel_id, title, description, image, code_url, demo_url, tags)
    return jsonify({'success': True})

# --- FORMATIONS ---

@app.route('/admin/api/formations', methods=['POST'])
@login_required
def admin_add_formation():
    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    institution = data.get('institution', '').strip()
    status = data.get('status', 'en_cours')
    if not title or not description:
        return jsonify({'error': 'Titre et description requis'}), 400
    if status not in ('en_cours', 'terminee'):
        status = 'en_cours'
    add_formation(title, description, institution, status)
    return jsonify({'success': True})

@app.route('/admin/api/formations/<int:form_id>', methods=['PUT', 'DELETE'])
@login_required
def admin_modify_formation(form_id):
    if request.method == 'DELETE':
        delete_formation(form_id)
        return jsonify({'status': 'deleted'})

    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    institution = data.get('institution', '').strip()
    status = data.get('status', 'en_cours')
    if not title or not description:
        return jsonify({'error': 'Titre et description requis'}), 400
    if status not in ('en_cours', 'terminee'):
        status = 'en_cours'
    update_formation(form_id, title, description, institution, status)
    return jsonify({'success': True})

# --- MESSAGES ---

@app.route('/admin/api/messages/<int:msg_id>/read', methods=['POST'])
@login_required
def admin_read_message(msg_id):
    mark_message_read(msg_id)
    return jsonify({'status': 'read'})

@app.route('/admin/api/messages/<int:msg_id>', methods=['DELETE'])
@login_required
def admin_delete_message(msg_id):
    delete_message(msg_id)
    return jsonify({'status': 'deleted'})

# --- SMTP CONFIG ---

@app.route('/admin/api/smtp', methods=['POST'])
@login_required
def admin_save_smtp():
    data = request.get_json()
    config = get_config()
    config['smtp_email'] = data.get('smtp_email', config.get('smtp_email', ''))
    config['smtp_app_password'] = data.get('smtp_app_password', config.get('smtp_app_password', ''))
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    return jsonify({'success': True})

@app.route('/admin/api/smtp/test', methods=['POST'])
@login_required
def admin_test_smtp():
    config = get_config()
    smtp_email = config.get('smtp_email', '')
    smtp_pass = config.get('smtp_app_password', '')
    smtp_server = config.get('smtp_server', 'smtp.gmail.com')
    smtp_port = config.get('smtp_port', 587)
    admin_email = config.get('admin_email', '')

    if not smtp_email or not smtp_pass:
        return jsonify({'success': False, 'message': "SMTP non configuré. Renseignez l'email et le mot de passe d'application."}), 400

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_email, smtp_pass)
        server.quit()
        return jsonify({'success': True, 'message': 'Connexion SMTP réussie ! Un email de test va être envoyé.'})
    except smtplib.SMTPAuthenticationError:
        return jsonify({'success': False, 'message': "Échec d'authentification. Vérifiez l'email et le mot de passe d'application."}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {e}'}), 400

if __name__ == '__main__':
    app.run(debug=True)
