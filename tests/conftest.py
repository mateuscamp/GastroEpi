"""Configuração comum da suíte."""

import os

# A casca Qt (Fase 5) roda sem display no CI e na máquina do agente.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
