from pathlib import Path
import sys


RAIZ_PROJETO = Path(__file__).resolve().parents[1]

if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))
