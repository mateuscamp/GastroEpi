"""Tipos e regras do domínio clínico (ADR-0004), em pydantic estrito (Princípio V).

- `listas`: listas fechadas (sexo, parentesco, segmento, Paris, histologia, indicação…);
- `paciente`, `exame`, `lesao`: os registros e as classificações derivadas deles;
- `cpf`, `datas`, `campos`: normalização da entrada; `erros`: mensagens em pt-BR;
- `ficticios`: gerador de pacientes fictícios com semente, para a demo e os testes.

Não importa outro módulo do projeto e não faz I/O (ADR-0002).
"""
