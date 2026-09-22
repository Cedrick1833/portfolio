import os
import re
import json
import hmac
import secrets
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
SECRET_FILE = os.path.join(BASE_DIR, '.secret_key')
DATABASE = os.path.join(BASE_DIR, 'portfolio.db')


def load_secret_key():
    """Clé secrète de session: vient de l'environnement (SECRET_KEY) ou d'un
    fichier local .secret_key (gitignoré, généré une fois). Jamais en dur dans le code."""
    env_key = (os.environ.get('SECRET_KEY') or '').strip()
    if env_key:
        return env_key
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, 'r', encoding='utf-8') as f:
            stored = f.read().strip()
        if stored:
            return stored
    key = secrets.token_hex(32)
    with open(SECRET_FILE, 'w', encoding='utf-8') as f:
        f.write(key)
    try:
        os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass
    return key


app.secret_key = load_secret_key()

FORCE_HTTPS = os.environ.get('FORCE_HTTPS') == '1' or (os.environ.get('PA_DOMAIN') or '') != ''
MAX_UPLOAD_MB = 15
app.config.update(
    SECRET_KEY=app.secret_key,
    MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=FORCE_HTTPS,
    PERMANENT_SESSION_LIFETIME=8 * 60 * 60,
    FORCE_HTTPS=FORCE_HTTPS,
)

@app.after_request
def add_no_cache(resp):
    """Empêche le cache navigateur sur le HTML (mises à jour admin visibles à chaque visite).
    Le CSS/JS versionnés (?v=) sont mis en cache pour un affichage rapide."""
    if resp.content_type and 'text/html' in resp.content_type:
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    elif resp.content_type and ('javascript' in resp.content_type or 'text/css' in resp.content_type):
        resp.headers['Cache-Control'] = 'public, max-age=3600'
    elif request.path.startswith('/static/uploads/'):
        # Les fichiers uploadés sont versionnés (?v=mtime) : un cache long,
        # fiable et immuable rend l'affichage du CV et des certificats instantané.
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            key TEXT NOT NULL,
            attempted_at REAL NOT NULL
        )
    ''')
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

def versioned_url(url):
    """Renvoie l'URL avec ?v= basé sur la date de modification du fichier.
    Un URL stable tant que le fichier ne change pas => le navigateur le met en
    cache et l'affichage du CV / certificats devient instantané."""
    if not url:
        return url
    base = url.split('?')[0]
    if not base.startswith('/static/'):
        return url
    try:
        fs_path = os.path.join(BASE_DIR, base.lstrip('/').replace('/', os.sep))
        version = int(os.path.getmtime(fs_path) * 1000)
    except OSError:
        version = 0
    return f"{base}?v={version}"

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
    certifications = [dict(row) for row in rows]
    for cert in certifications:
        cert['file_url_v'] = versioned_url(cert.get('file_url') or '')
    return certifications

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

# ---------- SÉCURITÉ ----------

EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
ALLOWED_IMAGES = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
ALLOWED_DOCS = ALLOWED_IMAGES | {'.pdf'}

RATE_WINDOW = 900  # 15 minutes


def is_rate_limited(scope, key, limit, window=RATE_WINDOW):
    now = time.time()
    cutoff = now - window
    db = get_db()
    db.execute('DELETE FROM rate_limits WHERE scope = ? AND attempted_at < ?', (scope, cutoff))
    db.commit()
    count = db.execute(
        'SELECT COUNT(*) FROM rate_limits WHERE scope = ? AND key = ?',
        (scope, key)
    ).fetchone()[0]
    return count >= limit


def record_attempt(scope, key):
    db = get_db()
    db.execute(
        'INSERT INTO rate_limits (scope, key, attempted_at) VALUES (?, ?, ?)',
        (scope, key, time.time())
    )
    db.commit()


def reset_attempts(scope, key):
    db = get_db()
    db.execute('DELETE FROM rate_limits WHERE scope = ? AND key = ?', (scope, key))
    db.commit()


def client_ip():
    return request.remote_addr or 'unknown'


def get_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


@app.before_request
def enforce_https():
    if app.config.get('FORCE_HTTPS') and request.url.startswith('http://'):
        proto = request.headers.get('X-Forwarded-Proto', 'http')
        if proto != 'https':
            return redirect(request.url.replace('http://', 'https://', 1))


@app.before_request
def csrf_protect():
    if request.method == 'GET' or not request.path.startswith('/admin'):
        return
    token = request.headers.get('X-CSRF-Token') or ''
    if not token:
        token = request.form.get('_csrf', '')
    if not token:
        token = (request.get_json(silent=True) or {}).get('_csrf', '')
    expected = session.get('csrf_token', '')
    if not token or not hmac.compare_digest(str(token), str(expected)):
        if request.path == '/admin':
            return redirect(url_for('admin_login', error='csrf'))
        return jsonify({'error': 'Jeton CSRF invalide ou expiré.'}), 403


@app.context_processor
def inject_csrf_token():
    return {'csrf_token': get_csrf_token()}


CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://ui-avatars.com; "
    "frame-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; "
    "connect-src 'self'; upgrade-insecure-requests"
)


@app.after_request
def add_security_headers(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    resp.headers.setdefault('Content-Security-Policy', CSP)
    if app.config.get('FORCE_HTTPS'):
        resp.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return resp


@app.errorhandler(413)
def request_too_large(e):
    if request.path.startswith('/admin'):
        return jsonify({'error': f'Fichier trop volumineux (maximum {MAX_UPLOAD_MB} Mo).'}), 413
    return jsonify({'error': 'Requête trop volumineuse.'}), 413


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith(('/admin', '/api')):
        return jsonify({'error': 'Ressource introuvable.'}), 404
    return e


@app.errorhandler(405)
def method_not_allowed(e):
    if request.path.startswith(('/admin', '/api')):
        return jsonify({'error': 'Méthode non autorisée.'}), 405
    return e


def get_admin_email():
    return (get_config().get('admin_email') or '').strip()


def admin_password_valid(email, password):
    """Vérifie les identifiants admin. Mot de passe stocké hashé (hashé dès la
    première connexion si la config contient encore un mot de passe en clair)."""
    expected_email = get_admin_email()
    if not expected_email or (email or '').strip() != expected_email:
        return False
    if not isinstance(password, str) or not password:
        return False
    config = get_config()
    pw_hash = config.get('admin_password_hash') or ''
    if pw_hash:
        return check_password_hash(pw_hash, password)
    legacy = config.get('admin_password')
    if legacy is None or not isinstance(legacy, str):
        return False
    if hmac.compare_digest(str(legacy), str(password)):
        config['admin_password_hash'] = generate_password_hash(password)
        config.pop('admin_password', None)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        return True
    return False


def validate_upload(file_storage, allowed_ext):
    """Valide un upload: nom sécurisé, extension autorisée et signature du fichier."""
    filename = secure_filename(file_storage.filename or '')
    ext = os.path.splitext(filename)[1].lower()
    if not ext or ext not in allowed_ext:
        raise ValueError('extension')
    file_storage.seek(0)
    head = file_storage.read(16)
    file_storage.seek(0)
    if ext == '.webp':
        ok = head[:4] == b'RIFF' and head[8:12] == b'WEBP'
    else:
        signatures = {
            '.pdf': b'%PDF',
            '.jpg': b'\xff\xd8\xff',
            '.jpeg': b'\xff\xd8\xff',
            '.png': b'\x89PNG\r\n\x1a\n',
            '.gif': b'GIF8',
        }
        ok = head.startswith(signatures[ext])
    if not ok:
        raise ValueError('contenu')
    return filename, ext

# ---------- ROUTES ----------

@app.route('/')
def index():
    certifications = get_certifications()
    certifications_count = len(certifications)
    formations = get_formations()
    realisations_count = len(get_realisations())
    formations_count = len(formations)

    cv_list = get_uploads('cv')
    cv_url = versioned_url(cv_list[0]['url']) if cv_list else ''
    cv_name = cv_list[0]['filename'] if cv_list else ''

    photo_list = get_uploads('photo')
    photo_url = versioned_url(photo_list[0]['url']) if photo_list else ''

    return render_template(
        'index.html',
        certifications=certifications,
        formations=formations,
        certifications_count=certifications_count,
        realisations_count=realisations_count,
        formations_count=formations_count,
        cv_url=cv_url,
        cv_name=cv_name,
        photo_url=photo_url,
    )

# --- PUBLIC API ---

@app.route('/api/contact', methods=['POST'])
def api_contact():
    data = request.get_json(silent=True) or {}
    nom = str(data.get('nom') or '').strip()[:100]
    email = str(data.get('email') or '').strip()[:254]
    message = str(data.get('message') or '').strip()[:5000]

    if not nom or not email or not message:
        return jsonify({'error': 'Tous les champs sont requis.'}), 400
    if not EMAIL_RE.match(email):
        return jsonify({'error': 'Adresse email invalide.'}), 400
    if is_rate_limited('contact', client_ip(), 5):
        return jsonify({'error': 'Trop de messages envoyés. Réessayez plus tard.'}), 429

    save_message(nom, email, message)
    record_attempt('contact', client_ip())
    sent, _ = send_email(nom, email, message)

    return jsonify({'success': True, 'email_sent': sent})

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
        return jsonify({'filename': c['filename'], 'url': versioned_url(c['url'])})
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
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    error = None
    if request.args.get('error') == 'csrf':
        error = 'Session expirée, veuillez vous reconnecter.'
    if request.method == 'POST':
        email = str(request.form.get('email', ''))
        password = str(request.form.get('password', ''))
        ip = client_ip()
        if is_rate_limited('login', ip, 8):
            error = 'Trop de tentatives de connexion. Réessayez dans quelques minutes.'
        elif admin_password_valid(email, password):
            config = get_config()
            was_legacy = not (config.get('admin_password_hash') or '')
            session.clear()
            session.permanent = True
            session['admin_logged_in'] = True
            session['csrf_token'] = secrets.token_hex(32)
            if was_legacy:
                session['needs_password_change'] = True
            reset_attempts('login', ip)
            return redirect(url_for('admin_dashboard'))
        else:
            record_attempt('login', ip)
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
        smtp_configured=bool(config.get('smtp_email') and config.get('smtp_app_password')),
        needs_password_change=bool(session.get('needs_password_change'))
    )

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin/api/security/password', methods=['POST'])
@login_required
def admin_change_password():
    data = request.get_json(silent=True) or {}
    current = str(data.get('current_password', '') or '')
    new_password = str(data.get('new_password', '') or '')
    if len(new_password) < 10:
        return jsonify({'error': 'Le mot de passe doit contenir au moins 10 caractères.'}), 400
    if not admin_password_valid(get_admin_email(), current):
        return jsonify({'error': 'Mot de passe actuel incorrect.'}), 403
    config = get_config()
    config['admin_password_hash'] = generate_password_hash(new_password)
    config.pop('admin_password', None)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    session.pop('needs_password_change', None)
    return jsonify({'success': True})

# --- ADMIN API ROUTES ---

@app.route('/admin/api/upload/photo', methods=['POST'])
@login_required
def admin_upload_photo():
    if 'photo' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    try:
        filename, _ = validate_upload(file, ALLOWED_IMAGES)
    except ValueError as e:
        return jsonify({'error': 'Format non autorisé. Utilisez une image JPG, PNG, GIF ou WebP.'}), 400
    for f in os.listdir(PHOTO_FOLDER):
        os.remove(os.path.join(PHOTO_FOLDER, f))
    delete_records('photo')
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
    try:
        filename, _ = validate_upload(file, ALLOWED_DOCS)
    except ValueError:
        return jsonify({'error': 'Format non autorisé. Utilisez un PDF ou une image.'}), 400
    filename = f"{int(time.time())}_{filename}"
    file.save(os.path.join(CERTS_FOLDER, filename))
    url = f'/static/uploads/certs/{filename}'
    record_upload('cert', filename, file.filename, url)
    return jsonify({'filename': filename, 'url': url})

@app.route('/admin/api/cert/<filename>', methods=['DELETE'])
@login_required
def admin_delete_cert(filename):
    name = os.path.basename(filename)
    filepath = os.path.join(CERTS_FOLDER, secure_filename(name))
    if not filepath.startswith(os.path.abspath(CERTS_FOLDER) + os.sep):
        return jsonify({'error': 'Chemin invalide'}), 400
    if os.path.exists(filepath):
        os.remove(filepath)
        delete_records('cert', name)
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
    try:
        filename, _ = validate_upload(file, ALLOWED_DOCS)
    except ValueError:
        return jsonify({'error': 'Format non autorisé. Utilisez un PDF ou une image.'}), 400
    for f in os.listdir(CV_FOLDER):
        os.remove(os.path.join(CV_FOLDER, f))
    delete_records('cv')
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
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        status = data.get('status', 'obtenue')
    if not title or not description:
        return jsonify({'error': 'Titre et description requis'}), 400
    if status not in ('obtenue', 'en_cours'):
        status = 'obtenue'
    cert_id = add_certification(title, description, status)
    if file:
        try:
            _, ext = validate_upload(file, ALLOWED_DOCS)
        except ValueError:
            delete_certification(cert_id)
            return jsonify({'error': 'Format non autorisé. Utilisez un PDF ou une image.'}), 400
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

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
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
    try:
        _, ext = validate_upload(file, ALLOWED_DOCS)
    except ValueError:
        return jsonify({'error': 'Format non autorisé. Utilisez un PDF ou une image.'}), 400
    file_url = get_cert_file(cert_id)
    if file_url:
        old = os.path.basename(file_url)
        old_path = os.path.join(CERTIF_FILES_FOLDER, old)
        if os.path.exists(old_path):
            os.remove(old_path)
    filename = f"cert_{cert_id}_{int(time.time())}{ext}"
    file.save(os.path.join(CERTIF_FILES_FOLDER, filename))
    url = f'/static/uploads/certifs/{filename}'
    attach_cert_file(cert_id, file.filename, url)
    return jsonify({'filename': filename, 'url': url})

# --- REALISATIONS ---

@app.route('/admin/api/realisations', methods=['POST'])
@login_required
def admin_add_realisation():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    image = (data.get('image') or '').strip()
    code_url = (data.get('code_url') or '').strip()
    demo_url = (data.get('demo_url') or '').strip()
    tags = (data.get('tags') or '').strip()
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

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    image = (data.get('image') or '').strip()
    code_url = (data.get('code_url') or '').strip()
    demo_url = (data.get('demo_url') or '').strip()
    tags = (data.get('tags') or '').strip()
    if not title or not description:
        return jsonify({'error': 'Titre et description requis'}), 400
    update_realisation(rel_id, title, description, image, code_url, demo_url, tags)
    return jsonify({'success': True})

# --- FORMATIONS ---

@app.route('/admin/api/formations', methods=['POST'])
@login_required
def admin_add_formation():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    institution = (data.get('institution') or '').strip()
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

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    institution = (data.get('institution') or '').strip()
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
    data = request.get_json(silent=True) or {}
    config = get_config()
    config['smtp_email'] = (data.get('smtp_email') or config.get('smtp_email', '')).strip()
    config['smtp_app_password'] = (data.get('smtp_app_password') or config.get('smtp_app_password', '')).strip()
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
        return jsonify({'success': True, 'message': 'Connexion SMTP réussie !'})
    except smtplib.SMTPAuthenticationError:
        return jsonify({'success': False, 'message': "Échec d'authentification. Vérifiez l'email et le mot de passe d'application."}), 400
    except Exception:
        return jsonify({'success': False, 'message': 'Impossible de se connecter au serveur SMTP.'}), 400

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
