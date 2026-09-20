# Release readiness — Portaria Control

## Invariantes implementadas
- Isolamento multi-tenant em consultas e mutações operacionais.
- RBAC explícito para administrador e operação.
- Sessão revalidada contra usuário/condomínio ativos.
- CSRF global e logout somente POST.
- Rate limit de login persistido em PostgreSQL, com retenção contínua.
- Auditoria transacional para mutações críticas e consulta pelo administrador do condomínio.
- Entrada e saída com operador e horário; uma única visita aberta por visitante/condomínio garantida no banco.
- Cadastro mestre de visitante separado da presença física.
- Encomendas com custódia central, retirada identificada e estados legados sem retorno ao fluxo de entrega na porta.
- Fotos fora do repositório e rota tenant-authorized preparada para armazenamento privado.
- Migrations forward-only com checksum; migrations aplicadas não podem ser reescritas.
- Health/readiness, Gunicorn, pool PostgreSQL, headers de segurança e request correlation.
- CI com compile, testes, pip check, higiene de artefatos e fail-closed de configuração.

## Gates antes de considerar release empresarial encerrada
1. Configurar e validar armazenamento privado de fotos no ambiente de produção, incluindo upload, webcam, leitura autorizada e política de retenção.
2. Executar teste de restore real do PostgreSQL a partir de backup e registrar RPO/RTO observado.
3. Adicionar testes de integração PostgreSQL concorrentes no CI; os contratos estáticos atuais não substituem integração.
4. Executar smoke autenticado de produção para admin e funcionário em cada fluxo crítico.
5. Consolidar o CSS acumulado depois da aprovação visual, removendo overrides mortos sem alterar comportamento.
6. Definir retenção de PII, fotos e audit logs conforme política do condomínio/LGPD.
7. Implementar módulos de segunda fase: autorizações prévias, ocorrências/livro digital, prestadores recorrentes e passagem de turno.

## Regra de mudança
Toda alteração que envolva comportamento deve ser avaliada em frontend, backend, tenant scope, autorização, transação, banco, auditoria, segurança, testes, observabilidade e recuperação. Migrations são imutáveis após aplicação.
