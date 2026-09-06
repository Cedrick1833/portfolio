# Portfolio — Cedrick B. Kabengele

Portfolio personnel d'ingénieur DevSecOps : architecture microservices, cybersécurité, réseaux & télécoms.

## Fonctionnalités

- Page vitrine responsive (mobile + desktop) avec animations
- Section **réalisations**, **certifications** (fichiers PDF) et **formations**
- **Back-office admin** : gestion complète des réalisations, certifications, formations, CV et messages
- Compteurs de statistiques dynamiques (certifications, projets, formations)
- Formulaire de contact (messages stockés en base / envoi mail optionnel via SMTP)

## Technologies

- **Backend** : Flask (Python)
- **Base de données** : SQLite (`portfolio.db`)
- **Frontend** : HTML / CSS / JavaScript, Bootstrap 5, animations CSS personnalisées

## Installation locale

```bash
# 1. Cloner le dépôt
git clone <votre-url>
cd <dossier>

# 2. Créer un environnement virtuel et installer les dépendances
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 3. Lancer le serveur
python app.py
```

Le site est accessible sur `http://127.0.0.1:5000`.

## Administration

- Page admin : `/admin`
- Les identifiants admin sont stockés dans `config.json` (non versionné — fichier ignoré par git, à créer soi-même).

Exemple de `config.json` :
```json
{
  "admin_email": "votre@email.com",
  "admin_password": "votre-mot-de-passe",
  "smtp_email": "",
  "smtp_app_password": "",
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587
}
```

## Sécurité

- `config.json` (identifiants) est ignoré par git et **ne doit jamais être committé**.
- `portfolio.db` (données) est ignoré par git.

## Déploiement

Ce projet est une application **Flask avec une base SQLite** : il nécessite un hébergeur capable d'exécuter un backend Python (ex. Render, Railway, PythonAnywhere). **GitHub Pages ne sert que du contenu statique** et ne peut pas exécuter cette application.