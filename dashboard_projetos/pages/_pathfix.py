"""
Importado no topo de cada página para garantir que utils/ seja encontrado.
Funciona no Windows, OneDrive, Streamlit Cloud e Linux.
"""
import sys, os
from pathlib import Path

# pages/ -> dashboard_projetos/
ROOT = Path(__file__).resolve().parent.parent
for p in [str(ROOT), str(ROOT / "utils")]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
