from flask import Blueprint, render_template, request, jsonify

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
