from flask import Blueprint, render_template, request, jsonify, g, redirect, url_for

from database.models import (
    total_visitantes_ativos,
    total_entradas_hoje,
    total_saidas_hoje,
    total_visitantes_cadastrados,
    total_moradores,
    ultima_entrada,
    ultimas_entradas_dashboard,
)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if getattr(g, "current_user", None) and g.current_user.get("nivel") == "platform_admin":
        return redirect(url_for("platform_admin.condominios"))
    cpf_pre = request.args.get("cpf", "")
    ultima_nome, ultima_hora = ultima_entrada()

    return render_template(
        "index.html",
        cpf_pre=cpf_pre,
        total_ativos=total_visitantes_ativos(),
        entradas_hoje=total_entradas_hoje(),
        saidas_hoje=total_saidas_hoje(),
        total_cadastrados=total_visitantes_cadastrados(),
        total_moradores=total_moradores(),
        ultima_nome=ultima_nome,
        ultima_hora=ultima_hora,
        ultimas_entradas=ultimas_entradas_dashboard(5),
    )


@main_bp.route("/resumo_ajax")
def resumo_ajax():
    if getattr(g, "current_user", None) and g.current_user.get("nivel") == "platform_admin":
        return jsonify({"erro": "Recurso disponível apenas no contexto de um condomínio."}), 403
    ultima_nome, ultima_hora = ultima_entrada()
    return jsonify({
        "ativos": total_visitantes_ativos(),
        "entradas": total_entradas_hoje(),
        "saidas": total_saidas_hoje(),
        "cadastrados": total_visitantes_cadastrados(),
        "moradores": total_moradores(),
        "ultima_nome": ultima_nome,
        "ultima_hora": ultima_hora,
    })
