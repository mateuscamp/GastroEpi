"""Único módulo que abre o banco (SQLCipher via sqlcipher3, ADR-0003).

Toda mutação de paciente ou catálogo grava o evento de auditoria na mesma transação.
"""
