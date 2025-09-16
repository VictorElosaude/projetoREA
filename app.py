import os
import pandas as pd
import requests
import json
import plotly.express as px
import numpy as np
from datetime import date, datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from flask import jsonify, session

# Carrega as variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key")

USERNAME = os.environ.get("APP_USERNAME")
PASSWORD = os.environ.get("APP_PASSWORD")
JSON_DATA_URL = os.environ.get("JSON_DATA_URL")
GOOGLE_CHAT_WEBHOOK_URL = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")

# ---------------------------------------------------
# QUESTÕES REA (1..59) + FLAGS para marcar MANUAL/AUTO
# ---------------------------------------------------

# Lista completa (1 a 59) com textos idênticos ao relatório REA
todas_questoes_rea = {
    1: "Ano dos dados informados",
    2: "E-mail do responsável pela Ouvidoria",
    3: "Telefone de contato",
    4: "[REANÁLISE] A Ouvidoria recebeu algum requerimento de reanálise assistencial?",
    5: "[REANÁLISE] Por que a Ouvidoria não recebeu requerimentos de reanálise assistencial?",
    6: "[REANÁLISE] Quantidade de requerimentos de reanálise convertidos em manifestação de ouvidoria",
    11: "[MANIFESTAÇÃO] A operadora recebeu manifestações próprias?",
    12: "[CANAL] Quantidade de manifestações recebidas pelo canal E-mail",
    13: "[CANAL] Quantidade de manifestações recebidas pelo canal Telefone",
    14: "[CANAL] Quantidade de manifestações recebidas pelo canal Site",
    15: "[CANAL] Quantidade de manifestações recebidas pelo canal Aplicativo ou Redes sociais da operadora",
    16: "[CANAL] Quantidade de manifestações recebidas pelo canal Presencialmente",
    17: "[CANAL] Quantidade de manifestações recebidas por outros canais",
    18: "[TEMA] Quantidade de manifestações sobre o tema Administrativo",
    19: "[TEMA] Quantidade de manifestações sobre o tema Cobertura assistencial",
    20: "[TEMA] Quantidade de manifestações sobre o tema Financeiro",
    21: "[TEMA] Quantidade de manifestações sobre o tema Rede credenciada/referenciada",
    22: "[TEMA] Quantidade de manifestações sobre o tema Serviço de Atendimento ao Cliente (SAC)",
    23: "[TIPO] Quantidade de manifestações do tipo Consulta",
    24: "[TIPO] Quantidade de manifestações do tipo Denúncia",
    25: "[TIPO] Quantidade de manifestações do tipo Elogio",
    26: "[TIPO] Quantidade de manifestações do tipo Reclamação",
    27: "[TIPO] Quantidade de manifestações do tipo Sugestão",
    28: "[RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema Administrativo",
    29: "[RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema Cobertura assistencial",
    30: "[RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema Financeiro",
    31: "[RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema Rede credenciada/referenciada",
    32: "[RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema SAC",
    33: "[RECLAMAÇÕES - TIPO] Quantidade de RECLAMAÇÕES vindas do tipo de contrato Coletivo adesão",
    34: "[RECLAMAÇÕES - TIPO] Quantidade de RECLAMAÇÕES vindas do tipo de contrato Coletivo empresarial",
    35: "[RECLAMAÇÕES - TIPO] Quantidade de RECLAMAÇÕES vindas do tipo de contrato Individual/Familiar",
    36: "[RECLAMAÇÕES - TIPO] Quantidade de RECLAMAÇÕES vindas de Outro tipo de contrato",
    37: "[RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Beneficiário ou interlocutor",
    38: "[RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Corretor",
    39: "[RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Gestor contrato coletivo",
    40: "[RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Prestador de serviços",
    41: "[RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Outros demandantes",
    42: "[INDICADORES] Tempo Médio de Resposta da Ouvidoria (TMRO)",
    43: "[INDICADORES] Percentual de Resposta Dentro do Prazo (PRDP)",
    44: "[INDICADORES] Percentual de Resposta Dentro de Prazo Pactuado (PRDPP)",
    45: "[INDICADORES] Percentual de Resposta Fora do Prazo (PRFP)",
    46: "[INDICADORES] Motivo(s) para o não cumprimento do prazo",
    47: "[AVALIAÇÃO-OUVIDORIA] A Ouvidoria possui avaliação de seu atendimento?",
    48: "[AVALIAÇÃO-OUVIDORIA] Informar o total de respondentes",
    49: "[AVALIAÇÃO-OUVIDORIA] De uma forma geral, como o seu atendimento foi avaliado?",
    50: "[RECOMENDAÇÕES] A Ouvidoria fez recomendações para melhoria do processo de trabalho da operadora?",
    51: "[RECOMENDAÇÕES] Informar, resumidamente, as recomendações propostas",
    52: "[RECOMENDAÇÕES] Por que a ouvidoria não fez recomendações de melhoria?",
    53: "[RECOMENDAÇÕES] Como considera o estágio de implementação das recomendações feitas em 2023?",
    54: "[ESTRUTURA] Quantas pessoas compõem exclusivamente a unidade de Ouvidoria?",
    55: "[DIVULGAÇÃO] Como a operadora divulga a existência da Ouvidoria?",
    56: "[ACOMPANHAMENTO] A Ouvidoria acompanha o desempenho da operadora na Notificação de Intermediação Preliminar (NIP)?",
    57: "[ACOMPANHAMENTO] A Ouvidoria tomou alguma ação para tentar reduzir a quantidade de NIPs? Se sim, descreva",
    58: "[ACOMPANHAMENTO] A Ouvidoria conhece o IDSS da operadora e a pesquisa de satisfação junto ao consumidor que o integra?",
    59: "[ACOMPANHAMENTO] A Ouvidoria fez alguma sugestão de melhoria com base nesses documentos? Se sim, descreva."
}

# Flags para identificar se a questão é AUTO (respondida pelo sistema) ou MANUAL
# Marque aqui as questões que deseja que apareçam como MANUAL no dropdown
questoes_flags = {
    49: "MANUAL",
    52: "MANUAL",
    57: "MANUAL",
    59: "MANUAL",
    11: "MANUAL",
}

def get_questoes_manuais():
    """
    Retorna lista de strings no formato "N) Texto da Questão" apenas para as questões
    marcadas como MANUAL no dicionário questoes_flags.
    """
    return [f"{num}) {todas_questoes_rea[num]}" for num in sorted(todas_questoes_rea.keys()) if questoes_flags.get(num) == "MANUAL"]

# ---------------------------------------------------
# Funções auxiliares existentes (mantidas)
# ---------------------------------------------------

def get_data_from_url():
    """
    Obtém os dados JSON diretamente da URL do Ploomnes.
    """
    try:
        response = requests.get(JSON_DATA_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter dados da URL: {e}")
        send_to_chat = globals().get('send_to_chat', None)
        if callable(send_to_chat):
            send_to_chat(f"Alerta: Erro ao obter dados do Ploomnes. URL: {JSON_DATA_URL}. Erro: {e}")
        return None

def calculate_working_days(start_date, end_date):
    """
    Calcula o número de dias úteis entre duas datas (excluindo sábados e domingos).
    """
    if pd.isna(start_date) or pd.isna(end_date):
        return None
    start_date = start_date.date()
    end_date = end_date.date()
    return np.busday_count(start_date, end_date)

def log_access(username, ip_address):
    """
    Registra um evento de login bem-sucedido em um arquivo de log.
    """
    log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Usuário: {username} - IP: {ip_address}\n"
    try:
        with open('access_log.txt', 'a') as f:
            f.write(log_entry)
    except IOError as e:
        print(f"Erro ao escrever no arquivo de log: {e}")

def send_to_chat(message):
    """
    Envia uma mensagem de notificação para o Google Chat via webhook.
    """
    if not GOOGLE_CHAT_WEBHOOK_URL:
        print("URL do webhook do Google Chat não configurada.")
        return
    headers = {'Content-Type': 'application/json; charset=UTF-8'}
    data = {'text': message}
    try:
        response = requests.post(GOOGLE_CHAT_WEBHOOK_URL, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        print("Mensagem enviada com sucesso para o Google Chat.")
    except requests.exceptions.RequestException as e:
        print(f"Falha ao enviar mensagem para o Google Chat: {e}")

# ---------------------------------------------------
# Processamento dos dados
# ---------------------------------------------------

def process_data(data, start_date=None, end_date=None):
    """
    Processa os dados e retorna um dicionário com todos os indicadores do relatório.
    """
    if not data:
        return None
    df = pd.DataFrame(data)

    col_mapping = {
        '*Tipo da Manifestação': 'tipo_manifestacao',
        '*Tema da Manifestação': 'tema_manifestacao',
        '*Forma de Entrada do Contato': 'forma_entrada_contato',
        '*Data da manifestação': 'data_manifestacao',
        '*Data da Resposta': 'data_resposta',
        'Atendimento para:': 'atendimento_para',
        '* Vínculo com o  beneficiário referenciado': 'vinculo_beneficiario',
    }
    missing_cols = [col for col in col_mapping.keys() if col not in df.columns]
    if missing_cols:
        message = f"Alerta: As seguintes colunas não foram encontradas no JSON do Ploomnes: {', '.join(missing_cols)}."
        send_to_chat(message)
    df.rename(columns={key: val for key, val in col_mapping.items() if key in df.columns}, inplace=True)
    if 'data_manifestacao' in df.columns:
        df['data_manifestacao'] = pd.to_datetime(df['data_manifestacao'])
        df['data_manifestacao_formatada'] = df['data_manifestacao'].dt.strftime('%d/%m/%Y')
    if 'data_resposta' in df.columns:
        df['data_resposta'] = pd.to_datetime(df['data_resposta'])
        df['data_resposta_formatada'] = df['data_resposta'].dt.strftime('%d/%m/%Y')
    if start_date and end_date:
        df = df[(df['data_manifestacao'] >= start_date) & (df['data_manifestacao'] <= end_date)]
    relatorio = {}
    ano_atual = date.today().year
    relatorio['ano_dados_informados'] = ano_atual
    relatorio['email_responsavel'] = "cleide@elosaude.com.br"
    relatorio['telefone_contato'] = "(48)3298-5555"
    df_reanalise = df[df['tipo_manifestacao'] == 'Reanálise'] if 'tipo_manifestacao' in df.columns else pd.DataFrame()
    quantitativo_reanalise = len(df_reanalise)
    relatorio['quantitativo_reanalise'] = quantitativo_reanalise
    relatorio['recebeu_reanalise'] = "SIM" if quantitativo_reanalise > 0 else "NÃO"
    relatorio['conversao_reanalise'] = 2
    relatorio['motivo_conversao'] = "Recebimento de documentação incompleta, necessitando documentação complementar para avaliação da auditoria médica."
    if 'forma_entrada_contato' in df.columns:
        quantitativo_proprias = len(df)
        relatorio['quantitativo_manifestacoes_proprias'] = quantitativo_proprias
        relatorio['recebeu_manifestacao_propria'] = "SIM" if quantitativo_proprias > 0 else "NÃO"
    else:
        relatorio['quantitativo_manifestacoes_proprias'] = 0
        relatorio['recebeu_manifestacao_propria'] = "NÃO"
    contagem_canais = df['forma_entrada_contato'].value_counts().to_dict() if 'forma_entrada_contato' in df.columns else {}
    relatorio['quantitativo_canais'] = contagem_canais
    contagem_temas = df['tema_manifestacao'].value_counts().to_dict() if 'tema_manifestacao' in df.columns else {}
    relatorio['quantitativo_temas'] = contagem_temas
    contagem_tipos = df['tipo_manifestacao'].value_counts().to_dict() if 'tipo_manifestacao' in df.columns else {}
    relatorio['quantitativo_tipos'] = contagem_tipos
    df_reclamacoes = df[df['tipo_manifestacao'] == 'Reclamação'] if 'tipo_manifestacao' in df.columns else pd.DataFrame()
    relatorio['reclamacoes_por_tema'] = df_reclamacoes['tema_manifestacao'].value_counts().to_dict() if 'tema_manifestacao' in df_reclamacoes.columns else {}
    df_reclamacoes_coletivo_empresarial = df_reclamacoes[df_reclamacoes['atendimento_para'] == 'Coletivo empresarial'] if 'atendimento_para' in df_reclamacoes.columns else pd.DataFrame()
    df_reclamacoes_coletivo_adesao = df_reclamacoes[df_reclamacoes['atendimento_para'] == 'Coletivo adesão'] if 'atendimento_para' in df_reclamacoes.columns else pd.DataFrame()
    df_reclamacoes_individual_familiar = df_reclamacoes[df_reclamacoes['atendimento_para'] == 'Individual/Familiar'] if 'atendimento_para' in df_reclamacoes.columns else pd.DataFrame()
    relatorio['reclamacoes_coletivo_adesao'] = len(df_reclamacoes_coletivo_adesao)
    relatorio['reclamacoes_coletivo_empresarial'] = len(df_reclamacoes_coletivo_empresarial)
    relatorio['reclamacoes_individual_familiar'] = len(df_reclamacoes_individual_familiar)
    relatorio['reclamacoes_outros_contratos'] = 0
    df_reclamacoes_beneficiario = df_reclamacoes[df_reclamacoes['atendimento_para'] == 'Beneficiário'] if 'atendimento_para' in df_reclamacoes.columns else pd.DataFrame()
    relatorio['reclamacoes_beneficiario'] = len(df_reclamacoes_beneficiario)
    relatorio['reclamacoes_corretor'] = 0
    relatorio['reclamacoes_gestor'] = 0
    relatorio['reclamacoes_prestador'] = 0
    relatorio['reclamacoes_outros_demandantes'] = 0
    contagem_vinculo = df['vinculo_beneficiario'].value_counts().to_dict() if 'vinculo_beneficiario' in df.columns else {}
    relatorio['quantitativo_vinculo_beneficiario'] = contagem_vinculo
    df_com_resposta = df[df['data_resposta'].notna()].copy() if 'data_resposta' in df.columns else pd.DataFrame()
    total_com_resposta = len(df_com_resposta)

    if total_com_resposta > 0 and 'data_manifestacao' in df_com_resposta.columns and 'data_resposta' in df_com_resposta.columns:
        df_com_resposta['dias_uteis_resposta'] = df_com_resposta.apply(lambda row: calculate_working_days(row['data_manifestacao'], row['data_resposta']), axis=1)
        tmro = df_com_resposta['dias_uteis_resposta'].mean()
        relatorio['tmro'] = round(tmro, 2) if not pd.isna(tmro) else 0
        dentro_prazo_7dias = df_com_resposta[df_com_resposta['dias_uteis_resposta'] <= 7]
        prdp = (len(dentro_prazo_7dias) / total_com_resposta) * 100
        relatorio['prdp'] = round(prdp, 2) if not pd.isna(prdp) else 0
        dentro_prazo_pactuado = df_com_resposta[(df_com_resposta['dias_uteis_resposta'] > 7) & (df_com_resposta['dias_uteis_resposta'] <= 30)]
        prdpp = (len(dentro_prazo_pactuado) / total_com_resposta) * 100
        relatorio['prdpp'] = round(prdpp, 2) if not pd.isna(prdpp) else 0
        fora_prazo = df_com_resposta[df_com_resposta['dias_uteis_resposta'] > 30]
        prfp = (len(fora_prazo) / total_com_resposta) * 100
        relatorio['prfp'] = round(prfp, 2) if not pd.isna(prfp) else 0
    else:
        relatorio['tmro'] = 0
        relatorio['prdp'] = 0
        relatorio['prdpp'] = 0
        relatorio['prfp'] = 0
    relatorio['motivo_nao_cumprimento_prazo'] = "Afetado pela dependência de retorno da rede prestadora envolvida para conclusão final da manifestação."
    relatorio['possui_avaliacao_atendimento'] = "NÃO"
    relatorio['total_respondentes'] = "Verificar fonte"
    relatorio['como_avaliacao'] = "Verificar fonte"
    relatorio['fez_recomendacoes'] = "SIM"
    relatorio['recomendacoes_propostas'] = "Recomendou-se conduzir através de linguajar mais acessível as negativas entregues aos beneficiários, proporcionando uma transmissão de maior clareza nas razões pelas quais foram negadas suas solicitações."
    relatorio['estagio_implementacao'] = "Não houve recomendações propostas no período anterior"
    relatorio['pessoas_unidade_ouvidoria'] = 1
    relatorio['divulgacao_ouvidoria'] = "Site, Email"
    relatorio['acompanha_nip'] = "SIM"
    relatorio['acoes_para_reduzir_nips'] = "Sim, a condução de analise conjunta entre a ouvidoria e demais áreas envolvidas, a fim de proporcionar analise com maior minucia e realizar o atendimento de solicitações cabíveis previamente a notificação, adiantando o entendimento do processo e possíveis consequências da resposta da ouvidoria."
    relatorio['conhece_idss_pesquisa_satisfacao'] = "SIM"
    relatorio['sugestao_melhoria_documentos'] = "Não"
    return relatorio

# ---------------------------------------------------
# Geração do PDF (ajustada para imprimir as questões com o número original)
# ---------------------------------------------------

def generate_pdf_report(relatorio, questoes_manuais=None):
    """
    Gera o PDF do relatório REA. Se houver questoes_manuais (lista de dicts
    com 'questao' e 'resposta'), imprime cada 'questao' exatamente como veio
    (ex.: '49) Texto...') para preservar o número original.
    """
    doc = SimpleDocTemplate("relatorio_rea.pdf", pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    styles['Normal'].leading = 14
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], alignment=TA_CENTER, fontSize=14)
    story.append(Paragraph("<b>Operadora:</b> 417297 - ELOSAÚDE - ASSOCIAÇÃO DE ASSISTÊNCIA À SAÚDE", header_style))
    story.append(Paragraph("<b>Processo Número nº:</b> 33910028928202421", header_style))
    story.append(Paragraph("<b>Ouvidoria - REA-Ouvidorias</b>", header_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("----------------------------------------------------------------------------------------------------------------------------------------", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Eu CLEIDE DE CALDAS NOGUEIRA, declaro que enviei as informações abaixo da operadora ELOSAÚDE - ASSOCIAÇÃO DE ASSISTÊNCIA À SAÚDE (417297) conforme solicitado.", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"1) Ano dos dados informados: {date.today().year}", styles['Normal']))
    story.append(Paragraph(f"2) E-mail do responsável pela Ouvidoria: {relatorio.get('email_responsavel', '')}", styles['Normal']))
    story.append(Paragraph(f"3) Telefone de contato: {relatorio.get('telefone_contato', '')}", styles['Normal']))
    story.append(Paragraph(f"4) [REANÁLISE] A Ouvidoria recebeu algum requerimento de reanálise assistencial em {date.today().year}?: {relatorio.get('recebeu_reanalise', '')}", styles['Normal']))
    story.append(Paragraph(f"5) [REANÁLISE] Por que a Ouvidoria não recebeu requerimentos de reanálise assistencial?: {'Não houve requerimentos no período' if relatorio.get('recebeu_reanalise') == 'NÃO' else relatorio.get('motivo_conversao', '')}", styles['Normal']))
    story.append(Paragraph(f"6) [REANÁLISE] Quantidade de requerimentos de reanálise convertidos em manifestação de ouvidoria: {relatorio.get('conversao_reanalise', 0)}", styles['Normal']))
    story.append(Paragraph(f"11) [MANIFESTAÇÃO] A operadora recebeu manifestações próprias?: {relatorio.get('recebeu_manifestacao_propria', '')}", styles['Normal']))
    story.append(Paragraph(f"12) [CANAL] Quantidade de manifestações recebidas pelo canal E-mail: {relatorio.get('quantitativo_canais', {}).get('E-mail', 0)}", styles['Normal']))
    story.append(Paragraph(f"13) [CANAL] Quantidade de manifestações recebidas pelo canal Telefone: {relatorio.get('quantitativo_canais', {}).get('Telefone', 0)}", styles['Normal']))
    story.append(Paragraph(f"14) [CANAL] Quantidade de manifestações recebidas pelo canal Site: {relatorio.get('quantitativo_canais', {}).get('Site', 0)}", styles['Normal']))
    story.append(Paragraph(f"15) [CANAL] Quantidade de manifestações recebidas pelo canal Aplicativo ou Redes sociais da operadora: {relatorio.get('quantitativo_canais', {}).get('Aplicativo ou Redes sociais da operadora', 0)}", styles['Normal']))
    story.append(Paragraph(f"16) [CANAL] Quantidade de manifestações recebidas pelo canal Presencialmente: {relatorio.get('quantitativo_canais', {}).get('Presencialmente', 0)}", styles['Normal']))
    story.append(Paragraph(f"17) [CANAL] Quantidade de manifestações recebidas por outros canais: {relatorio.get('quantitativo_canais', {}).get('Outros', 0)}", styles['Normal']))
    story.append(Paragraph(f"18) [TEMA] Quantidade de manifestações sobre o tema Administrativo: {relatorio.get('quantitativo_temas', {}).get('Administrativo', 0)}", styles['Normal']))
    story.append(Paragraph(f"19) [TEMA] Quantidade de manifestações sobre o tema Cobertura assistencial: {relatorio.get('quantitativo_temas', {}).get('Cobertura assistencial', 0)}", styles['Normal']))
    story.append(Paragraph(f"20) [TEMA] Quantidade de manifestações sobre o tema Financeiro: {relatorio.get('quantitativo_temas', {}).get('Financeiro', 0)}", styles['Normal']))
    story.append(Paragraph(f"21) [TEMA] Quantidade de manifestações sobre o tema Rede credenciada/referenciada: {relatorio.get('quantitativo_temas', {}).get('Rede credenciada/referenciada', 0)}", styles['Normal']))
    story.append(Paragraph(f"22) [TEMA] Quantidade de manifestações sobre o tema Serviço de Atendimento ao Cliente (SAC): {relatorio.get('quantitativo_temas', {}).get('Serviço de Atendimento ao Cliente (SAC)', 0)}", styles['Normal']))
    story.append(Paragraph(f"23) [TIPO] Quantidade de manifestações do tipo Consulta: {relatorio.get('quantitativo_tipos', {}).get('Consulta', 0)}", styles['Normal']))
    story.append(Paragraph(f"24) [TIPO] Quantidade de manifestações do tipo Denúncia: {relatorio.get('quantitativo_tipos', {}).get('Denúncia', 0)}", styles['Normal']))
    story.append(Paragraph(f"25) [TIPO] Quantidade de manifestações do tipo Elogio: {relatorio.get('quantitativo_tipos', {}).get('Elogio', 0)}", styles['Normal']))
    story.append(Paragraph(f"26) [TIPO] Quantidade de manifestações do tipo Reclamação: {relatorio.get('quantitativo_tipos', {}).get('Reclamação', 0)}", styles['Normal']))
    story.append(Paragraph(f"27) [TIPO] Quantidade de manifestações do tipo Sugestão: {relatorio.get('quantitativo_tipos', {}).get('Sugestão', 0)}", styles['Normal']))
    story.append(Paragraph(f"28) [RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema Administrativo: {relatorio.get('reclamacoes_por_tema', {}).get('Administrativo', 0)}", styles['Normal']))
    story.append(Paragraph(f"29) [RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema Cobertura assistencial: {relatorio.get('reclamacoes_por_tema', {}).get('Cobertura assistencial', 0)}", styles['Normal']))
    story.append(Paragraph(f"30) [RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema Financeiro: {relatorio.get('reclamacoes_por_tema', {}).get('Financeiro', 0)}", styles['Normal']))
    story.append(Paragraph(f"31) [RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema Rede credenciada/referenciada: {relatorio.get('reclamacoes_por_tema', {}).get('Rede credenciada/referenciada', 0)}", styles['Normal']))
    story.append(Paragraph(f"32) [RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema SAC: {relatorio.get('reclamacoes_por_tema', {}).get('Serviço de Atendimento ao Cliente (SAC)', 0)}", styles['Normal']))
    story.append(Paragraph(f"33) [RECLAMAÇÕES - TIPO] Quantidade de RECLAMAÇÕES vindas do tipo de contrato Coletivo adesão: {relatorio.get('reclamacoes_coletivo_adesao', 0)}", styles['Normal']))
    story.append(Paragraph(f"34) [RECLAMAÇÕES - TIPO] Quantidade de RECLAMAÇÕES vindas do tipo de contrato Coletivo empresarial: {relatorio.get('reclamacoes_coletivo_empresarial', 0)}", styles['Normal']))
    story.append(Paragraph(f"35) [RECLAMAÇÕES - TIPO] Quantidade de RECLAMAÇÕES vindas do tipo de contrato Individual/Familiar: {relatorio.get('reclamacoes_individual_familiar', 0)}", styles['Normal']))
    story.append(Paragraph(f"36) [RECLAMAÇÕES - TIPO] Quantidade de RECLAMAÇÕES vindas de Outro tipo de contrato: {relatorio.get('reclamacoes_outros_contratos', 0)}", styles['Normal']))
    story.append(Paragraph(f"37) [RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Beneficiário ou interlocutor: {relatorio.get('reclamacoes_beneficiario', 0)}", styles['Normal']))
    story.append(Paragraph(f"38) [RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Corretor: {relatorio.get('reclamacoes_corretor', 0)}", styles['Normal']))
    story.append(Paragraph(f"39) [RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Gestor contrato coletivo: {relatorio.get('reclamacoes_gestor', 0)}", styles['Normal']))
    story.append(Paragraph(f"40) [RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Prestador de serviços: {relatorio.get('reclamacoes_prestador', 0)}", styles['Normal']))
    story.append(Paragraph(f"41) [RECLAMAÇÕES - DEMANDANTE] Quantidade de RECLAMAÇÕES realizadas por Outros demandantes: {relatorio.get('reclamacoes_outros_demandantes', 0)}", styles['Normal']))
    story.append(Paragraph(f"42) [INDICADORES] Tempo Médio de Resposta da Ouvidoria (TMRO): {relatorio.get('tmro', 0)}", styles['Normal']))
    story.append(Paragraph(f"43) [INDICADORES] Percentual de Resposta Dentro do Prazo (PRDP): {relatorio.get('prdp', 0)}", styles['Normal']))
    story.append(Paragraph(f"44) [INDICADORES] Percentual de Resposta Dentro de Prazo Pactuado (PRDPP): {relatorio.get('prdpp', 0)}", styles['Normal']))
    story.append(Paragraph(f"45) [INDICADORES] Percentual de Resposta Fora do Prazo (PRFP): {relatorio.get('prfp', 0)}", styles['Normal']))
    story.append(Paragraph(f"46) [INDICADORES] Motivo(s) para o não cumprimento do prazo: {relatorio.get('motivo_nao_cumprimento_prazo', '')}", styles['Normal']))
    story.append(Paragraph(f"47) [AVALIAÇÃO-OUVIDORIA] A Ouvidoria possui avaliação de seu atendimento?: {relatorio.get('possui_avaliacao_atendimento', '')}", styles['Normal']))
    story.append(Paragraph(f"48) [AVALIAÇÃO-OUVIDORIA] Informar o total de respondentes: {relatorio.get('total_respondentes', '')}", styles['Normal']))
    
    # Substitui as respostas automáticas pelas manuais, se existirem
    resposta_q49 = next((qm['resposta'] for qm in (questoes_manuais or []) if qm['questao'].startswith("49)")), relatorio.get('como_avaliacao', ''))
    story.append(Paragraph(f"49) [AVALIAÇÃO-OUVIDORIA] De uma forma geral, como o seu atendimento foi avaliado?: {resposta_q49}", styles['Normal']))

    story.append(Paragraph(f"50) [RECOMENDAÇÕES] A Ouvidoria fez recomendações para melhoria do processo de trabalho da operadora?: {relatorio.get('fez_recomendacoes', '')}", styles['Normal']))
    story.append(Paragraph(f"51) [RECOMENDAÇÕES] Informar, resumidamente, as recomendações propostas.: {relatorio.get('recomendacoes_propostas', '')}", styles['Normal']))

    resposta_q52 = next((qm['resposta'] for qm in (questoes_manuais or []) if qm['questao'].startswith("52)")), 'Não aplicável' if relatorio.get('fez_recomendacoes') == 'SIM' else relatorio.get('motivo_nao_cumprimento_prazo', ''))
    story.append(Paragraph(f"52) [RECOMENDAÇÕES] Por que a ouvidoria não fez recomendações de melhoria?: {resposta_q52}", styles['Normal']))

    story.append(Paragraph(f"53) [RECOMENDAÇÕES] Como considera o estágio de implementação das recomendações feitas em 2023?: {relatorio.get('estagio_implementacao', '')}", styles['Normal']))
    story.append(Paragraph(f"54) [ESTRUTURA] Quantas pessoas compõem exclusivamente a unidade de Ouvidoria?: {relatorio.get('pessoas_unidade_ouvidoria', 0)}", styles['Normal']))
    story.append(Paragraph(f"55) [DIVULGAÇÃO] Como a operadora divulga a existência da Ouvidoria?: {relatorio.get('divulgacao_ouvidoria', '')}", styles['Normal']))
    story.append(Paragraph(f"56) [ACOMPANHAMENTO] A Ouvidoria acompanha o desempenho da operadora na Notificação de Intermediação Preliminar (NIP)?: {relatorio.get('acompanha_nip', '')}", styles['Normal']))

    resposta_q57 = next((qm['resposta'] for qm in (questoes_manuais or []) if qm['questao'].startswith("57)")), relatorio.get('acoes_para_reduzir_nips', ''))
    story.append(Paragraph(f"57) [ACOMPANHAMENTO] A Ouvidoria tomou alguma ação para tentar reduzir a quantidade de NIPs? Se sim, descreva.: {resposta_q57}", styles['Normal']))

    story.append(Paragraph(f"58) [ACOMPANHAMENTO] A Ouvidoria conhece o Índice de Desempenho da Saúde Suplementar (IDSS) da operadora e a pesquisa de satisfação junto ao consumidor que o integra?: {relatorio.get('conhece_idss_pesquisa_satisfacao', '')}", styles['Normal']))

    resposta_q59 = next((qm['resposta'] for qm in (questoes_manuais or []) if qm['questao'].startswith("59)")), relatorio.get('sugestao_melhoria_documentos', ''))
    story.append(Paragraph(f"59) [ACOMPANHAMENTO] A Ouvidoria fez alguma sugestão de melhoria com base nesses documentos? Se sim, descreva.: {resposta_q59}", styles['Normal']))

    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"Este documento foi gerado automaticamente pelo sistema Protocolo Eletrônico em {datetime.now().strftime('%d/%m/%Y')}.", styles['Normal']))
    doc.build(story)
    return "relatorio_rea.pdf"

# ---------------------------------------------------
# ROTAS
# ---------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == USERNAME and password == PASSWORD:
            ip_address = request.remote_addr
            log_access(username, ip_address)
            session['logged_in'] = True
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Credenciais inválidas.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard", methods=['GET', 'POST'])
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    start_date = pd.to_datetime(start_date_str) if start_date_str else None
    end_date = pd.to_datetime(end_date_str) if end_date_str else None
    data = get_data_from_url()
    relatorio = process_data(data, start_date, end_date)
    if relatorio is None:
        return "Erro ao obter dados. Verifique sua URL e a conexão.", 500

    color_palette = ["#59BEAF", "#467090", "#96E5E5", "#167F7F", '#931C76', '#9B182C']
    
    # Geração dos gráficos
    # --- Gráfico de Tipos de Manifestação (Pizza) ---
    df_tipos = pd.DataFrame(list(relatorio['quantitativo_tipos'].items()), columns=['Tipo', 'Quantidade']) if relatorio.get('quantitativo_tipos') else pd.DataFrame(columns=['Tipo', 'Quantidade'])
    df_tipos['Tipo_com_Quantidade'] = df_tipos.apply(lambda row: f"{row['Tipo']} ({row['Quantidade']})", axis=1)
    fig_tipos = px.pie(
        df_tipos,
        values='Quantidade',
        names='Tipo_com_Quantidade',
        title='Distribuição por Tipo de Manifestação',
        color_discrete_sequence=color_palette
    )
    fig_tipos.update_traces(
        textinfo='percent',
        textposition='inside',
        marker_line_width=1,
        marker_line_color='black',
        textfont=dict(size=17),
        hovertemplate="<b>%{label}</b><br>Quantidade: %{value}<br>Percentual: %{percent}<extra></extra>"
    )
    fig_tipos.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor='#e0e5ec',
        plot_bgcolor='#e0e5ec',
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=-0.2,
            title_text='',
            font=dict(size=17)
        )
    )
    div_tipos = fig_tipos.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
    )

    # --- Gráfico de Canais de Entrada (Pizza) ---
    df_canais = pd.DataFrame(list(relatorio['quantitativo_canais'].items()), columns=['Canal', 'Quantidade']) if relatorio.get('quantitativo_canais') else pd.DataFrame(columns=['Canal', 'Quantidade'])
    df_canais['Canal_com_Quantidade'] = df_canais.apply(lambda row: f"{row['Canal']} ({row['Quantidade']})", axis=1)
    fig_canais = px.pie(
        df_canais,
        values='Quantidade',
        names='Canal_com_Quantidade',
        title='Distribuição por Canal de Entrada',
        color_discrete_sequence=color_palette
    )
    fig_canais.update_traces(
        textinfo='percent',
        textposition='inside',
        marker_line_width=1,
        marker_line_color='black',
        textfont=dict(size=17),
        hovertemplate="<b>%{label}</b><br>Quantidade: %{value}<br>Percentual: %{percent}<extra></extra>"
    )
    fig_canais.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor='#e0e5ec',
        plot_bgcolor='#e0e5ec',
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=-0.2,
            title_text='',
            font=dict(size=17)
        )
    )
    div_canais = fig_canais.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
    )

    # --- Gráfico de Tema de Manifestação (Barras) ---
    df_temas = pd.DataFrame(list(relatorio['quantitativo_temas'].items()), columns=['Tema', 'Quantidade']) if relatorio.get('quantitativo_temas') else pd.DataFrame(columns=['Tema', 'Quantidade'])
    abreviacoes = {
        'Administrativo': 'Admin.',
        'Cobertura Assistencial': 'Cob. Assis.',
        'Financeiro': 'Financeiro',
        'Rede Credenciada/referenciada': 'Rede Cred/Ref',
        'Serviço de Atendimento ao Cliente (SAC)': 'SAC'
    }
    df_temas['Tema'] = df_temas['Tema'].str.strip().replace(abreviacoes)
    fig_temas = px.bar(
        df_temas,
        x='Tema',
        y='Quantidade',
        title='Quantidade por Tema de Manifestação',
        color_discrete_sequence=color_palette,
        text='Quantidade'
    )
    fig_temas.update_traces(
        textposition='outside',
        textfont_size=17,
        marker_color='#467090'
    )
    fig_temas.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_title="",
        yaxis_title="",
        paper_bgcolor='#e0e5ec',
        plot_bgcolor='#e0e5ec',
        xaxis=dict(tickfont=dict(size=17), title_font=dict(size=17)),
        yaxis=dict(tickfont=dict(size=17), showticklabels=False, title_font=dict(size=17))
    )
    div_temas = fig_temas.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
    )

    # --- Gráfico de Vínculo do Beneficiário (Barras) ---
    df_vinculo = pd.DataFrame(list(relatorio['quantitativo_vinculo_beneficiario'].items()), columns=['Vínculo', 'Quantidade']) if relatorio.get('quantitativo_vinculo_beneficiario') else pd.DataFrame(columns=['Vínculo', 'Quantidade'])
    fig_vinculo = px.bar(
        df_vinculo,
        x='Vínculo',
        y='Quantidade',
        title='Quantidade por Vínculo do Beneficiário',
        color_discrete_sequence=color_palette,
        text='Quantidade'
    )
    fig_vinculo.update_traces(
        textposition='outside',
        textfont_size=17,
        marker_color='#467090'
    )
    fig_vinculo.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_title="",
        yaxis_title="",
        paper_bgcolor='#e0e5ec',
        plot_bgcolor='#e0e5ec',
        xaxis=dict(tickfont=dict(size=17), title_font=dict(size=17)),
        yaxis=dict(tickfont=dict(size=17), showticklabels=False, title_font=dict(size=17))
    )
    div_vinculo = fig_vinculo.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
    )

    return render_template("dashboard.html",
        relatorio=relatorio,
        div_tipos=div_tipos,
        div_temas=div_temas,
        div_canais=div_canais,
        div_vinculo=div_vinculo,
        start_date=start_date_str,
        end_date=end_date_str,
        questoes_predefinidas=get_questoes_manuais()
    )

@app.route("/download-pdf", methods=['GET', 'POST'])
def download_pdf():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    data = get_data_from_url()
    relatorio = process_data(data)
    if relatorio is None:
        return "Erro ao obter dados para gerar o PDF.", 500
    questoes_manuais = []
    if request.method == 'POST':
        questoes_json = request.form.get('questoes_manuais')
        if questoes_json:
            try:
                questoes_manuais = json.loads(questoes_json)
            except json.JSONDecodeError:
                print("Erro ao decodificar JSON de questões manuais")
    pdf_path = generate_pdf_report(relatorio, questoes_manuais)
    return send_file(pdf_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)