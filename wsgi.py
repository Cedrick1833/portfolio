import os
import sys

# ---- ADAPTE ce chemin si ton dossier PythonAnywhere est différent ----
PROJECT_DIR = '/home/Cedrick1833/portfolio'

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.chdir(PROJECT_DIR)

from app import app as application  # noqa: E402