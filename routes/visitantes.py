import logging
import os
import uuid
import csv
import io
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect,
    flash, jsonify, url_for, current_app, session, g
)
from werkzeug.utils import secure_filename

from database.models import (
    cadastrar_visitante,
    listar_visitantes_paginado,
    buscar_visitantes,
    buscar_um_por_cpf,
    buscar_visitante_por_id,
    atualizar_visitante,
    remover_visitante,
    atualizar_foto_visitante,
    atualizar_observacao_visitante,
    atualizar_visita_ativa,
    registrar_entrada,
    registrar_saida,
    visitantes_ativos,
    buscar_ativos,
    historico_visitante,
    cpf_ja_cadastrado,
    listar_cpfs_visitantes,
    importar_visitantes_em_lotes,
    listar_unidades,
    buscar_moradores_ajax,
)
from utils.validators import (
    limpar_cpf, validar_cpf,
    EXTENSOES_FOTO_PERMITIDAS,
)
from utils.imagem import salvar_foto_webcam
from utils.storage import save_image
from utils.endereco import formatar_endereco_condominio
from utils.audit import registrar_auditoria
from utils.authz import roles_required

visitantes_bp = Blueprint("visitantes", __name__)
logger = logging.getLogger(__name__)


def _salvar_foto(arquivo_foto, foto_webcam_b64, pasta_fotos):
    os.makedirs(pasta_fotos, exist_ok=True)

    if arquivo_foto and arquivo_foto.filename:
        ext = os.path.splitext(secure_filename(arquivo_foto.filename))[1].lower()
        if ext not in EXTENSOES_FOTO_PERMITIDAS:
            return None, "Tipo de arquivo não permitido. Use JPG, PNG ou WEBP."
        nome = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
        arquivo_foto.save(os.path.join(pasta_fotos, nome))
        return nome, None

    if foto_webcam_b64:
        nome = salvar_foto_webcam(foto_webcam_b64, pasta_fotos)
        return nome, None

    return None, None


def _storage_ready():
    return all([os.getenv("S3_ENDPOINT_URL"), os.getenv("S3_BUCKET"), os.getenv("S3_ACCESS_KEY_ID"), os.getenv("S3_SECRET_ACCESS_KEY")])


def _save_photo_production(arquivo_foto, foto_webcam_b64):
    if foto_webcam_b64:
        return None, "Captura por webcam está temporariamente indisponível até o armazenamento privado ser configurado."
    if not arquivo_foto or not arquivo_foto.filename:
        return None, None
    if not _storage_ready():
        return None, "Upload de fotos está temporariamente indisponível."
    try:
        return save_image(arquivo_foto, g.tenant_id), None
    except (ValueError, RuntimeError):
        logger.exception("Falha ao persistir foto do visitante")
        return None, "Não foi possível armazenar a foto com segurança."


# ──────────────────────────────────────────────────────────────
# CADASTRO
# ──────────────────────────────────────────────────────────────

@visitantes_bp.route("/cadastro", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def cadastro():
    cpf_pre = request.args.get("cpf", "")
    unidades = listar_unidades()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip().upper()
        cpf  = limpar_cpf(request.form.get("cpf", ""))
        tipo = request.form.get("tipo", "").strip().upper()
        placa   = request.form.get("placa", "").strip().upper()
        marca   = request.form.get("marca", "").strip().upper()
        modelo  = request.form.get("modelo", "").strip().upper()
        observacao = request.form.get("observacao", "").strip().upper()
        endereco   = formatar_endereco_condominio(request.form.get("endereco", ""))
        unidade_id = request.form.get("unidade_id") or None
        morador_id = request.form.get("morador_id") or None

        if not nome:
            flash("Informe o nome do visitante.", "erro")
            return redirect(url_for("visitantes.cadastro", cpf=cpf_pre))

        if not cpf:
            flash("Informe o CPF do visitante.", "erro")
            return redirect(url_for("visitantes.cadastro", cpf=cpf_pre))

        if not validar_cpf(cpf):
            flash("CPF inválido. Verifique os dígitos.", "erro")
            return redirect(url_for("visitantes.cadastro", cpf=cpf))

        existente = cpf_ja_cadastrado(cpf)
        if existente:
            flash(f"CPF já cadastrado para: {existente['nome']}.", "erro")
            return redirect(url_for("visitantes.cadastro", cpf=cpf))

        arquivo_foto = request.files.get("foto")
        foto_webcam = request.form.get("foto_webcam", "").strip()
        if current_app.config.get("APP_ENV") == "production":
            nome_foto, erro_foto = _save_photo_production(arquivo_foto, foto_webcam)
        else:
            pasta_fotos = os.path.join(current_app.root_path, "static", "fotos")
            nome_foto, erro_foto = _salvar_foto(arquivo_foto, foto_webcam, pasta_fotos)
        if erro_foto:
            flash(erro_foto, "erro")
            return redirect(url_for("visitantes.cadastro", cpf=cpf))

        try:
            visitante_id = cadastrar_visitante(
                nome, cpf, tipo, placa, modelo, marca, nome_foto, observacao,
                endereco=endereco,
                entrada={
                    "endereco": "",
                    "usuario_id": session["usuario_id"],
                    "unidade_id": unidade_id,
                    "morador_id": morador_id,
                },
            )
        except ValueError as exc:
            flash(str(exc), "erro")
            return redirect(url_for("visitantes.cadastro", cpf=cpf))
        except Exception:
            logger.exception("Erro ao cadastrar visitante e registrar entrada")
            flash("Não foi possível concluir o cadastro do visitante.", "erro")
            return redirect(url_for("visitantes.cadastro", cpf=cpf))

        flash("Visitante cadastrado e entrada registrada com sucesso!", "sucesso")
        return redirect(url_for("visitantes.ativos"))

    return render_template("cadastro.html", cpf_pre=cpf_pre, unidades=unidades)


# ──────────────────────────────────────────────────────────────
# LISTAGEM
# ──────────────────────────────────────────────────────────────

@visitantes_bp.route("/visitantes", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def visitantes():
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = 20

    if request.method == "POST":
        termo = request.form.get("busca", "").strip()
        dados = buscar_visitantes(termo)
        if not dados:
            flash("Nenhum resultado encontrado.", "info")
        return render_template("visitantes.html", visitantes=dados,
                               pagina=1, total_paginas=1, total_registros=len(dados))

    dados, total = listar_visitantes_paginado(pagina, por_pagina)
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)

    return render_template("visitantes.html", visitantes=dados,
                           pagina=pagina, total_paginas=total_paginas, total_registros=total)


@visitantes_bp.route("/ativos")
@roles_required("admin", "funcionario")
def ativos():
    dados = visitantes_ativos()
    return render_template("ativos.html", visitantes=dados)


# ──────────────────────────────────────────────────────────────
# ENTRADA / SAÍDA
# ──────────────────────────────────────────────────────────────

@visitantes_bp.route("/entrada", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def entrada():
    unidades = listar_unidades()

    if request.method == "POST":
        cpf      = limpar_cpf(request.form.get("cpf", ""))
        endereco = formatar_endereco_condominio(request.form.get("endereco", ""))
        unidade_id = request.form.get("unidade_id") or None
        morador_id = request.form.get("morador_id") or None

        visitante = buscar_um_por_cpf(cpf)
        if not visitante:
            flash("Visitante não encontrado. Faça o cadastro primeiro.", "erro")
            return redirect(url_for("visitantes.cadastro", cpf=cpf))

        if not endereco:
            flash("Informe o endereço/destino da visita.", "erro")
            return redirect(url_for("visitantes.entrada"))

        try:
            registrar_entrada(visitante["id"], endereco,
                              usuario_id=session["usuario_id"],
                              unidade_id=unidade_id, morador_id=morador_id)
        except ValueError as exc:
            flash(str(exc), "erro")
            return redirect(url_for("visitantes.entrada"))
        except Exception:
            logger.exception("Erro ao registrar entrada")
            flash("Não foi possível registrar a entrada.", "erro")
            return redirect(url_for("visitantes.entrada"))
        flash("Entrada registrada com sucesso!", "sucesso")
        return redirect(url_for("visitantes.ativos"))

    return render_template("entrada.html", unidades=unidades)


@visitantes_bp.route("/saida/<int:id>", methods=["POST"])
@roles_required("admin", "funcionario")
def saida(id):
    try:
        alterou = registrar_saida(id, session["usuario_id"])
    except Exception:
        logger.exception("Erro ao registrar saída")
        flash("Não foi possível registrar a saída.", "erro")
        return redirect(url_for("visitantes.ativos"))
    if not alterou:
        flash("Não há visita ativa para este visitante.", "aviso")
        return redirect(url_for("visitantes.ativos"))
    flash("Saída registrada com sucesso!", "sucesso")
    return redirect(url_for("visitantes.ativos"))


# ──────────────────────────────────────────────────────────────
# EDITAR / REMOVER
# ──────────────────────────────────────────────────────────────

@visitantes_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def editar(id):
    visitante = buscar_visitante_por_id(id)
    if not visitante:
        flash("Visitante não encontrado.", "erro")
        return redirect(url_for("visitantes.visitantes"))

    if request.method == "POST":
        nome   = request.form.get("nome", "").strip().upper()
        cpf    = limpar_cpf(request.form.get("cpf", ""))
        tipo   = request.form.get("tipo", "").strip().upper()
        placa  = request.form.get("placa", "").strip().upper()
        modelo = request.form.get("modelo", "").strip().upper()
        marca  = request.form.get("marca", "").strip().upper()
        observacao = request.form.get("observacao", "").strip().upper()
        endereco = formatar_endereco_condominio(request.form.get("endereco", ""))

        if cpf and not validar_cpf(cpf):
            flash("CPF inválido. Verifique os dígitos.", "erro")
            return redirect(url_for("visitantes.editar", id=id))

        existente = cpf_ja_cadastrado(cpf, visitante_id=id)
        if existente:
            flash(f"CPF já cadastrado para outro visitante: {existente['nome']}.", "erro")
            return redirect(url_for("visitantes.editar", id=id))

        arquivo_foto = request.files.get("foto")
        foto_webcam = request.form.get("foto_webcam", "").strip()
        if current_app.config.get("APP_ENV") == "production":
            nome_foto, erro_foto = _save_photo_production(arquivo_foto, foto_webcam)
        else:
            pasta_fotos = os.path.join(current_app.root_path, "static", "fotos")
            nome_foto, erro_foto = _salvar_foto(arquivo_foto, foto_webcam, pasta_fotos)
        if erro_foto:
            flash(erro_foto, "erro")
            return redirect(url_for("visitantes.editar", id=id))

        if not nome_foto:
            nome_foto = visitante["foto"]

        atualizar_visitante(id, nome, cpf, tipo, placa, modelo, marca, nome_foto, observacao, endereco=endereco, usuario_id=session["usuario_id"])
        flash("Cadastro atualizado com sucesso!", "sucesso")
        return redirect(url_for("visitantes.visitantes"))

    return render_template("editar.html", visitante=visitante)


@visitantes_bp.route("/remover/<int:id>", methods=["POST"])
@roles_required("admin")
def remover(id):
    visitante = buscar_visitante_por_id(id)
    if not visitante:
        flash("Visitante não encontrado.", "erro")
        return redirect(url_for("visitantes.visitantes"))

    try:
        remover_visitante(id, session["usuario_id"])
        flash("Visitante removido com sucesso!", "sucesso")
    except ValueError as exc:
        flash(str(exc), "erro")
    return redirect(url_for("visitantes.visitantes"))


@visitantes_bp.route("/historico/<int:id>")
@roles_required("admin", "funcionario")
def historico(id):
    visitante = buscar_visitante_por_id(id)
    if not visitante:
        flash("Visitante não encontrado.", "erro")
        return redirect(url_for("visitantes.visitantes"))

    visitas = historico_visitante(id)
    return render_template("historico.html", visitante=visitante, visitas=visitas)


# ──────────────────────────────────────────────────────────────
# AJAX
# ──────────────────────────────────────────────────────────────

@visitantes_bp.route("/buscar_ajax")
@roles_required("admin", "funcionario")
def buscar_ajax():
    termo = request.args.get("q", "").strip()
    resultados = buscar_visitantes(termo)

    return jsonify([{
        "id": v["id"],
        "nome": v["nome"],
        "cpf": v["cpf"],
        "tipo": v.get("tipo") or "",
        "placa": v.get("placa") or "",
        "modelo": v.get("modelo") or "",
        "marca": v.get("marca") or "",
        "foto": v.get("foto") or "",
        "observacao": v.get("observacao") or "",
        "ultimo_endereco": v.get("ultimo_endereco") or "",
    } for v in resultados])


@visitantes_bp.route("/buscar_cpf_ajax", methods=["POST"])
@roles_required("admin", "funcionario")
def buscar_cpf_ajax():
    cpf = limpar_cpf(request.form.get("cpf", ""))
    visitante = buscar_um_por_cpf(cpf)
    if visitante:
        return jsonify({
            "nome": visitante["nome"],
            "cpf": visitante["cpf"],
            "tipo": visitante.get("tipo") or "",
            "placa": visitante.get("placa") or "",
            "modelo": visitante.get("modelo") or "",
        })
    return jsonify({"erro": "nao_encontrado"})


@visitantes_bp.route("/buscar_ativos_ajax")
@roles_required("admin", "funcionario")
def buscar_ativos_ajax():
    termo = request.args.get("q", "").strip()
    if not termo:
        return jsonify([])

    dados = buscar_ativos(termo)
    return jsonify([{
        "id": v["id"],
        "nome": v["nome"],
        "cpf": v["cpf"],
        "endereco": v.get("endereco") or "",
        "tipo": v.get("tipo") or "",
        "placa": v.get("placa") or "",
        "modelo": v.get("modelo") or "",
        "marca": v.get("marca") or "",
        "foto": v.get("foto") or "",
        "observacao": v.get("observacao") or "",
        "morador_nome": v.get("morador_nome") or "",
        "unidade_codigo": v.get("unidade_codigo") or "",
        "data_entrada": v["data_entrada"].isoformat() if v.get("data_entrada") else "",
    } for v in dados])


@visitantes_bp.route("/buscar_moradores_ajax")
@roles_required("admin", "funcionario")
def buscar_moradores_ajax_rota():
    termo = request.args.get("q", "").strip()
    if len(termo) < 2:
        return jsonify([])
    dados = buscar_moradores_ajax(termo)
    return jsonify([{
        "id": m["id"],
        "nome": m["nome"],
        "unidade_codigo": m.get("unidade_codigo") or "",
        "unidade_descricao": m.get("unidade_descricao") or "",
    } for m in dados])


@visitantes_bp.route("/entrada_ajax", methods=["POST"])
@roles_required("admin", "funcionario")
def entrada_ajax():
    try:
        visitante_id = request.form.get("id", "").strip()
        endereco    = formatar_endereco_condominio(request.form.get("endereco", ""))
        placa       = request.form.get("placa", "").strip().upper()
        marca       = request.form.get("marca", "").strip().upper()
        modelo      = request.form.get("modelo", "").strip().upper()
        observacao  = request.form.get("observacao", "").strip().upper()
        unidade_id  = request.form.get("unidade_id") or None
        morador_id  = request.form.get("morador_id") or None

        if not visitante_id:
            return jsonify({"status": "erro", "mensagem": "ID do visitante não informado."}), 400
        if not endereco:
            return jsonify({"status": "erro", "mensagem": "Informe o endereço/destino."}), 400

        registrar_entrada(
            visitante_id, endereco, placa, marca, modelo, observacao,
            session["usuario_id"], unidade_id, morador_id
        )
        return jsonify({"status": "ok"})

    except ValueError as exc:
        return jsonify({"status": "erro", "mensagem": str(exc)}), 400
    except Exception:
        logger.exception("Erro em /entrada_ajax")
        return jsonify({"status": "erro", "mensagem": "Não foi possível concluir a operação."}), 500


@visitantes_bp.route("/atualizar_observacao_ajax", methods=["POST"])
@roles_required("admin", "funcionario")
def atualizar_observacao_ajax():
    visitante_id = request.form.get("id", "").strip()
    observacao   = request.form.get("observacao", "").strip().upper()

    if not visitante_id:
        return jsonify({"status": "erro", "mensagem": "ID não informado."}), 400

    atualizar_observacao_visitante(visitante_id, observacao, session["usuario_id"])
    return jsonify({"status": "ok", "mensagem": "Observação atualizada."})


@visitantes_bp.route("/atualizar_foto_ajax", methods=["POST"])
@roles_required("admin", "funcionario")
def atualizar_foto_ajax():
    try:
        visitante_id  = request.form.get("id", "").strip()
        foto_base64   = request.form.get("foto", "").strip()

        if not visitante_id:
            return jsonify({"status": "erro", "mensagem": "ID não informado."}), 400
        if not foto_base64:
            return jsonify({"status": "erro", "mensagem": "Nenhuma imagem enviada."}), 400

        if current_app.config.get("APP_ENV") == "production":
            return jsonify({"status": "erro", "mensagem": "Captura por webcam está temporariamente indisponível até o armazenamento privado ser configurado."}), 503

        pasta = os.path.join(current_app.root_path, "static", "fotos")
        os.makedirs(pasta, exist_ok=True)
        nome_arquivo = salvar_foto_webcam(foto_base64, pasta)

        if not nome_arquivo:
            return jsonify({"status": "erro", "mensagem": "Falha ao salvar imagem."}), 400

        atualizar_foto_visitante(visitante_id, nome_arquivo, session["usuario_id"])
        return jsonify({"status": "ok", "mensagem": "Foto atualizada.", "foto": nome_arquivo})

    except Exception:
        logger.exception("Erro em /atualizar_foto_ajax")
        return jsonify({"status": "erro", "mensagem": "Não foi possível atualizar a foto."}), 500


# ──────────────────────────────────────────────────────────────
# IMPORTAÇÃO CSV
# ──────────────────────────────────────────────────────────────

@visitantes_bp.route("/importar_visitantes", methods=["GET", "POST"])
@roles_required("admin")
def importar_visitantes():
    if session.get("usuario_tipo") != "admin":
        flash("Apenas administradores podem acessar essa área.", "erro")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        arquivo = request.files.get("arquivo_csv")
        if not arquivo or arquivo.filename == "":
            flash("Selecione um arquivo CSV.", "erro")
            return redirect(url_for("visitantes.importar_visitantes"))

        try:
            conteudo = arquivo.read().decode("utf-8-sig")
            leitor   = csv.DictReader(io.StringIO(conteudo))

            importados, duplicados, erros = 0, 0, 0
            detalhes_erros = []
            cpfs_existentes  = listar_cpfs_visitantes()
            cpfs_no_arquivo  = set()
            para_importar    = []

            for i, linha in enumerate(leitor, start=2):
                try:
                    nome = (linha.get("nome") or "").strip().upper()
                    cpf  = limpar_cpf(linha.get("cpf") or "")

                    if not nome or not cpf:
                        erros += 1
                        detalhes_erros.append(f"Linha {i}: Nome ou CPF ausente")
                        continue
                    if not validar_cpf(cpf):
                        erros += 1
                        detalhes_erros.append(f"Linha {i}: CPF inválido")
                        continue

                    if cpf in cpfs_existentes or cpf in cpfs_no_arquivo:
                        duplicados += 1
                        continue

                    para_importar.append((
                        nome, cpf,
                        (linha.get("tipo") or "").strip().upper(),
                        (linha.get("placa") or "").strip().upper(),
                        (linha.get("modelo") or "").strip().upper(),
                        (linha.get("marca") or "").strip().upper(),
                        None,
                        (linha.get("observacao") or "").strip().upper(),
                    ))
                    cpfs_no_arquivo.add(cpf)

                except Exception:
                    logger.exception("Erro ao validar linha %s da importação", i)
                    erros += 1
                    detalhes_erros.append(f"Linha {i}: dados inválidos")

            if para_importar:
                importados = importar_visitantes_em_lotes(para_importar, usuario_id=session["usuario_id"])

            return render_template("importar_visitantes.html",
                                   importados=importados, duplicados=duplicados,
                                   erros=erros, detalhes_erros=detalhes_erros)

        except Exception as e:
            logger.exception("Erro ao processar CSV")
            flash("Não foi possível processar o arquivo CSV.", "erro")
            return redirect(url_for("visitantes.importar_visitantes"))

    return render_template("importar_visitantes.html",
                           importados=None, duplicados=None,
                           erros=None, detalhes_erros=[])
