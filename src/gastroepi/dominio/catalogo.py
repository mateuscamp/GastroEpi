"""Item de catálogo (comorbidade, sintoma): o nome que a lista mostra."""

from gastroepi.dominio.campos import ModeloDeDominio, TextoObrigatorio


class ItemDeCatalogo(ModeloDeDominio):
    nome: TextoObrigatorio
