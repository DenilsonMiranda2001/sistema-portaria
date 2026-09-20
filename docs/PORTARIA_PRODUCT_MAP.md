# Mapa operacional — Portaria Control

## Núcleo já existente
- Identidade multi-tenant por condomínio.
- Usuários de operação e administradores com RBAC.
- Moradores e unidades.
- Visitantes, cadastro, entrada, saída, ativos e histórico.
- Veículos vinculados ao visitante/entrada.
- Auditoria de mutações críticas.
- Encomendas por lote, código de retirada, histórico e notificação.
- Administração geral da plataforma.

## Fluxo operacional alvo
1. **Início**: busca rápida, pessoas no condomínio, entradas/saídas do dia e alertas operacionais.
2. **Cadastro**: cadastro mestre do visitante (nome, CPF, endereço, tipo, veículo e foto) separado da visita.
3. **Entrada**: visitante + destino interno (morador/unidade) + veículo da entrada + operador + horário.
4. **No condomínio**: fila em tempo real de acessos abertos, com destino e saída rápida.
5. **Visitantes**: cadastro mestre e histórico, sem confundir cadastro com presença atual.
6. **Moradores/unidades**: vínculo de ocupação e contato.
7. **Encomendas**: recebimento centralizado -> identificação da unidade/morador -> código de retirada -> notificação -> armazenamento central -> retirada identificada -> histórico.
8. **Administração do condomínio**: equipe, perfis, status e futuramente políticas/configurações operacionais.

## Lacunas que devem virar módulos/etapas
- Autorizações prévias de visitantes/prestadores.
- Ocorrências e livro digital da portaria.
- Prestadores recorrentes e janelas de acesso.
- Contatos úteis/emergência e instruções operacionais.
- Turnos/passagem de serviço.
- Auditoria consultável pelo administrador.
- Política de retenção de PII/fotos.
- Armazenamento privado definitivo de fotos.
- Evidência de retirada de encomenda (quem retirou já existe; assinatura/foto/PIN pode ser avaliado).
- Posição física opcional da encomenda caso o ponto central passe a ter prateleiras/armários.
- Relatórios operacionais sem transformar a portaria em dashboard analítico pesado.

## Regras de produto
- Cadastro mestre não representa presença.
- Visita aberta é a única fonte de verdade para “No condomínio”.
- Endereço residencial do visitante não é destino da visita.
- Toda entrada e saída deve manter operador e horário.
- Encomenda recebida no ponto central inicia aguardando retirada; não depende de entrega na porta.
- Ações críticas devem ser tenant-scoped, auditáveis e transacionais.
- Telas de operação devem ser compactas, legíveis, responsivas e orientadas a ação.
