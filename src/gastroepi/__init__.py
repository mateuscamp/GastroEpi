"""GastroEpi: registro offline de colonoscopia e epidemiologia de câncer colorretal.

Fronteiras em docs/adr/0002: o núcleo (dominio, cofre, auditoria, persistencia,
estatistica, exportacao, servicos) não conhece interface; as cascas (ui_qt, cli)
só entram no núcleo por servicos.
"""
