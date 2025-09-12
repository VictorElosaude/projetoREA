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
from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from flask import jsonify



# Carrega as variáveis de ambiente
load_dotenv()

app = Flask(__name__)

USERNAME = os.environ.get("APP_USERNAME")
PASSWORD = os.environ.get("APP_PASSWORD")
JSON_DATA_URL = os.environ.get("JSON_DATA_URL")
GOOGLE_CHAT_WEBHOOK_URL = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")

def get_data_from_url():
    """
    Obtém os dados JSON diretamente da URL do Ploomnes.
    """
    try:
        response = requests.get(JSON_DATA_URL)
        response.raise_for_status() # Lança um erro para status de erro (4xx, 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter dados da URL: {e}")
        # Envia notificação de erro ao chat
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
    
    working_days = np.busday_count(start_date, end_date)
    return working_days

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


def process_data(data, start_date=None, end_date=None):
    """
    Processa os dados e retorna um dicionário com todos os indicadores do relatório.
    Agora aceita filtros de data.
    """
    if not data:
        return None
        
    df = pd.DataFrame(data)

    # --- Mapeamento e verificação de colunas ---
    col_mapping = {
        '*Tipo da Manifestação': 'tipo_manifestacao',
        '*Tema da Manifestação': 'tema_manifestacao',
        '*Forma de Entrada do Contato': 'forma_entrada_contato',
        '*Data da manifestação': 'data_manifestacao',
        '*Data da Resposta': 'data_resposta',
        'Atendimento para:': 'atendimento_para',
        '* Vínculo com o  beneficiário referenciado': 'vinculo_beneficiario',
    }

    # Verifica quais colunas estão faltando e envia uma notificação
    missing_cols = [col for col in col_mapping.keys() if col not in df.columns]
    if missing_cols:
        message = f"Alerta: As seguintes colunas não foram encontradas no JSON do Ploomnes: {', '.join(missing_cols)}. O dashboard pode não exibir dados completos."
        send_to_chat(message)
    
    # Aplica o mapeamento apenas para as colunas que existem no DataFrame
    df.rename(columns={key: val for key, val in col_mapping.items() if key in df.columns}, inplace=True)

    # --- Formatação dos campos de data e hora ---
    if 'data_manifestacao' in df.columns:
        df['data_manifestacao'] = pd.to_datetime(df['data_manifestacao'])
        df['data_manifestacao_formatada'] = df['data_manifestacao'].dt.strftime('%d/%m/%Y')
    
    if 'data_resposta' in df.columns:
        df['data_resposta'] = pd.to_datetime(df['data_resposta'])
        df['data_resposta_formatada'] = df['data_resposta'].dt.strftime('%d/%m/%Y')

    # --- Aplicar filtro de data, se fornecido ---
    if start_date and end_date:
        df = df[(df['data_manifestacao'] >= start_date) & (df['data_manifestacao'] <= end_date)]

    # --- CÁLCULOS PARA O FORMULÁRIO REA ---
    relatorio = {}
    ano_atual = date.today().year

    # --- Seções de Campos Fixos (ITENS 1, 2, 3)
    relatorio['ano_dados_informados'] = ano_atual
    relatorio['email_responsavel'] = "cleide@elosaude.com.br"
    relatorio['telefone_contato'] = "(48)3298-5555"
    
    # --- Seção REANÁLISE (ITENS 4, 6) ---
    df_reanalise = df[df['tipo_manifestacao'] == 'Reanálise'] if 'tipo_manifestacao' in df.columns else pd.DataFrame()
    quantitativo_reanalise = len(df_reanalise)
    relatorio['quantitativo_reanalise'] = quantitativo_reanalise
    relatorio['recebeu_reanalise'] = "SIM" if quantitativo_reanalise > 0 else "NÃO"
    relatorio['conversao_reanalise'] = 2 # Valor fixo fornecido
    relatorio['motivo_conversao'] = "Recebimento de documentação incompleta, necessitando documentação complementar para avaliação da auditoria médica."

    # --- Seção MANIFESTAÇÃO (ITENS 11, 12-17) ---
    if 'forma_entrada_contato' in df.columns:
        df_manifestacoes_proprias = df[df['forma_entrada_contato'].isin(['E-mail', 'Telefone', 'Site', 'Aplicativo ou Redes sociais da operadora', 'Presencialmente'])]
        quantitativo_proprias = len(df_manifestacoes_proprias)
        relatorio['quantitativo_manifestacoes_proprias'] = quantitativo_proprias
        relatorio['recebeu_manifestacao_propria'] = "SIM" if quantitativo_proprias > 0 else "NÃO"
    else:
        relatorio['quantitativo_manifestacoes_proprias'] = 0
        relatorio['recebeu_manifestacao_propria'] = "NÃO"


    # --- Seção CANAL (ITENS 12-17) ---
    contagem_canais = df['forma_entrada_contato'].value_counts().to_dict() if 'forma_entrada_contato' in df.columns else {}
    relatorio['quantitativo_canais'] = contagem_canais

    # --- Seção TEMA (ITENS 18-22) ---
    contagem_temas = df['tema_manifestacao'].value_counts().to_dict() if 'tema_manifestacao' in df.columns else {}
    relatorio['quantitativo_temas'] = contagem_temas

    # --- Seção TIPO (ITENS 23-27) ---
    contagem_tipos = df['tipo_manifestacao'].value_counts().to_dict() if 'tipo_manifestacao' in df.columns else {}
    relatorio['quantitativo_tipos'] = contagem_tipos

    # --- Seção RECLAMAÇÕES - TEMA (ITENS 28-32) ---
    df_reclamacoes = df[df['tipo_manifestacao'] == 'Reclamação'] if 'tipo_manifestacao' in df.columns else pd.DataFrame()
    relatorio['reclamacoes_por_tema'] = df_reclamacoes['tema_manifestacao'].value_counts().to_dict() if 'tema_manifestacao' in df_reclamacoes.columns else {}

    # --- Seção RECLAMAÇÕES - TIPO CONTRATO (ITENS 33-36) ---
    df_reclamacoes_coletivo_empresarial = df_reclamacoes[df_reclamacoes['atendimento_para'] == 'Coletivo empresarial'] if 'atendimento_para' in df_reclamacoes.columns else pd.DataFrame()
    df_reclamacoes_coletivo_adesao = df_reclamacoes[df_reclamacoes['atendimento_para'] == 'Coletivo adesão'] if 'atendimento_para' in df_reclamacoes.columns else pd.DataFrame()
    df_reclamacoes_individual_familiar = df_reclamacoes[df_reclamacoes['atendimento_para'] == 'Individual/Familiar'] if 'atendimento_para' in df_reclamacoes.columns else pd.DataFrame()

    relatorio['reclamacoes_coletivo_adesao'] = len(df_reclamacoes_coletivo_adesao)
    relatorio['reclamacoes_coletivo_empresarial'] = len(df_reclamacoes_coletivo_empresarial)
    relatorio['reclamacoes_individual_familiar'] = len(df_reclamacoes_individual_familiar)
    relatorio['reclamacoes_outros_contratos'] = 0 # Valor fixo

    # --- Seção RECLAMAÇÕES - DEMANDANTE (ITENS 37-41) ---
    df_reclamacoes_beneficiario = df_reclamacoes[df_reclamacoes['atendimento_para'] == 'Beneficiário'] if 'atendimento_para' in df_reclamacoes.columns else pd.DataFrame()
    relatorio['reclamacoes_beneficiario'] = len(df_reclamacoes_beneficiario)
    relatorio['reclamacoes_corretor'] = 0 # Valor fixo
    relatorio['reclamacoes_gestor'] = 0 # Valor fixo
    relatorio['reclamacoes_prestador'] = 0 # Valor fixo
    relatorio['reclamacoes_outros_demandantes'] = 0 # Valor fixo
    
    # Contagem de vinculo com o beneficiario
    contagem_vinculo = df['vinculo_beneficiario'].value_counts().to_dict() if 'vinculo_beneficiario' in df.columns else {}
    relatorio['quantitativo_vinculo_beneficiario'] = contagem_vinculo
    
    # --- Seção INDICADORES (ITENS 42-45) ---
    df_com_resposta = df.dropna(subset=['data_resposta']) if 'data_resposta' in df.columns else pd.DataFrame()
    total_com_resposta = len(df_com_resposta)
    
    if total_com_resposta > 0 and 'data_manifestacao' in df_com_resposta.columns and 'data_resposta' in df_com_resposta.columns:
        # TMRO - Item 42
        df_com_resposta['dias_uteis_resposta'] = df_com_resposta.apply(lambda row: calculate_working_days(row['data_manifestacao'], row['data_resposta']), axis=1)
        tmro = df_com_resposta['dias_uteis_resposta'].mean()
        relatorio['tmro'] = round(tmro, 2) if not pd.isna(tmro) else 0

        # PRDP - Item 43
        dentro_prazo_7dias = df_com_resposta[df_com_resposta['dias_uteis_resposta'] <= 7]
        prdp = (len(dentro_prazo_7dias) / total_com_resposta) * 100
        relatorio['prdp'] = round(prdp, 2) if not pd.isna(prdp) else 0
        
        # PRDPP - Item 44
        dentro_prazo_pactuado = df_com_resposta[(df_com_resposta['dias_uteis_resposta'] > 7) & (df_com_resposta['dias_uteis_resposta'] <= 30)]
        prdpp = (len(dentro_prazo_pactuado) / total_com_resposta) * 100
        relatorio['prdpp'] = round(prdpp, 2) if not pd.isna(prdpp) else 0

        # PRFP - Item 45
        fora_prazo = df_com_resposta[df_com_resposta['dias_uteis_resposta'] > 30]
        prfp = (len(fora_prazo) / total_com_resposta) * 100
        relatorio['prfp'] = round(prfp, 2) if not pd.isna(prfp) else 0
    else:
        relatorio['tmro'] = 0
        relatorio['prdp'] = 0
        relatorio['prdpp'] = 0
        relatorio['prfp'] = 0

    relatorio['motivo_nao_cumprimento_prazo'] = "Afetado pela dependência de retorno da rede prestadora envolvida para conclusão final da manifestação."
    
    # --- Seção AVALIAÇÃO-OUVIDORIA (ITENS 47, 48, 49) ---
    relatorio['possui_avaliacao_atendimento'] = "NÃO"
    relatorio['total_respondentes'] = "Verificar fonte"
    relatorio['como_avaliacao'] = "Verificar fonte"

    # --- Seção RECOMENDAÇÕES (ITENS 50, 51, 52) ---
    relatorio['fez_recomendacoes'] = "SIM"
    relatorio['recomendacoes_propostas'] = "Recomendou-se conduzir através de linguajar mais acessível as negativas entregues aos beneficiários, proporcionando uma transmissão de maior clareza nas razões pelas quais foram negadas suas solicitações."
    relatorio['estagio_implementacao'] = "Não houve recomendações propostas no período anterior"

    # --- Seção ESTRUTURA (ITEM 54) ---
    relatorio['pessoas_unidade_ouvidoria'] = 1 # Valor fixo

    # --- Seção DIVULGAÇÃO (ITEM 55) ---
    relatorio['divulgacao_ouvidoria'] = "Site, Email" # Valor fixo

    # --- Seção ACOMPANHAMENTO (ITENS 56-59) ---
    relatorio['acompanha_nip'] = "SIM"
    relatorio['acoes_para_reduzir_nips'] = "Sim, a condução de analise conjunta entre a ouvidoria e demais áreas envolvidas, a fim de proporcionar analise com maior minucia e realizar o atendimento de solicitações cabíveis previamente a notificação, adiantando o entendimento do processo e possíveis consequências da resposta da ouvidoria."
    relatorio['conhece_idss_pesquisa_satisfacao'] = "SIM"
    relatorio['sugestao_melhoria_documentos'] = "Não"

    return relatorio

def generate_pdf_report(relatorio):
    """
    Gera o relatório em PDF com base no dicionário de relatório, seguindo o modelo.
    """
    doc = SimpleDocTemplate("relatorio_rea.pdf", pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    styles['Normal'].leading = 14 # Espaçamento entre as linhas

    # Criando um novo estilo para o cabeçalho.
    # O ReportLab não suporta .copy() para ParagraphStyle, então criamos um novo
    # e definimos as propriedades.
    header_style = ParagraphStyle('HeaderStyle')
    header_style.parent = styles['Normal']
    header_style.alignment = TA_CENTER
    header_style.fontSize = 14
    
    # Header - Apenas as 3 linhas do cabeçalho alteradas
    story.append(Paragraph("<b>Operadora:</b> 417297 - ELOSAÚDE - ASSOCIAÇÃO DE ASSISTÊNCIA À SAÚDE", header_style))
    story.append(Paragraph("<b>Processo Número nº:</b> 33910028928202421", header_style))
    story.append(Paragraph("<b>Ouvidoria - REA-Ouvidorias</b>", header_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Linha de separação
    story.append(Paragraph("----------------------------------------------------------------------------------------------------------------------------------------", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    # Restante do corpo do relatório, com o estilo 'Normal' intacto
    story.append(Paragraph("Eu CLEIDE DE CALDAS NOGUEIRA, declaro que enviei as informações abaixo da operadora ELOSAÚDE - ASSOCIAÇÃO DE ASSISTÊNCIA À SAÚDE (417297) conforme solicitado.", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"1) Ano dos dados informados: {date.today().year}", styles['Normal']))
    story.append(Paragraph(f"2) E-mail do responsável pela Ouvidoria: {relatorio.get('email_responsavel')}", styles['Normal']))
    story.append(Paragraph(f"3) Telefone de contato: {relatorio.get('telefone_contato')}", styles['Normal']))
    story.append(Paragraph(f"4) [REANÁLISE] A Ouvidoria recebeu algum requerimento de reanálise assistencial em {date.today().year}?: {relatorio.get('recebeu_reanalise')}", styles['Normal']))
    story.append(Paragraph(f"5) [REANÁLISE] Por que a Ouvidoria não recebeu requerimentos de reanálise assistencial em {date.today().year}?:", styles['Normal']))
    story.append(Paragraph(f"6) [REANÁLISE] Informar o quantitativo de requerimentos de reanálise recebidos em {date.today().year}: {relatorio.get('quantitativo_reanalise', 0)}", styles['Normal']))
    story.append(Paragraph(f"7) [REANÁLISE] Quantitativo de requerimentos de reanálise convertidos em autorização de cobertura: {relatorio.get('conversao_reanalise', 0)}", styles['Normal']))
    story.append(Paragraph(f"8) [REANÁLISE] Informar o principal motivo para conversão em autorização de cobertura: {relatorio.get('motivo_conversao')}", styles['Normal']))
    story.append(Paragraph(f"9) [MANIFESTAÇÃO] A Ouvidoria recebeu alguma manifestação própria de ouvidoria em {date.today().year}?: {relatorio.get('recebeu_manifestacao_propria')}", styles['Normal']))
    story.append(Paragraph(f"10) [MANIFESTAÇÃO] Por que a Ouvidoria não recebeu manifestações próprias de ouvidoria em {date.today().year}?:", styles['Normal']))
    story.append(Paragraph(f"11) [MANIFESTAÇÃO] Informar o quantitativo de manifestações próprias de ouvidoria recebidas em {date.today().year}: {relatorio.get('quantitativo_manifestacoes_proprias', 0)}", styles['Normal']))
    story.append(Paragraph(f"12) [CANAL] Quantidade de manifestações recebidas por E-mail: {relatorio.get('quantitativo_canais', {}).get('E-mail', 0)}", styles['Normal']))
    story.append(Paragraph(f"13) [CANAL] Quantidade de manifestações recebidas Presencialmente: {relatorio.get('quantitativo_canais', {}).get('Presencialmente', 0)}", styles['Normal']))
    story.append(Paragraph(f"14) [CANAL] Quantidade de manifestações recebidas pelas Redes Sociais: {relatorio.get('quantitativo_canais', {}).get('Aplicativo ou Redes sociais da operadora', 0)}", styles['Normal']))
    story.append(Paragraph(f"15) [CANAL] Quantidade de manifestações recebidas pelo Site: {relatorio.get('quantitativo_canais', {}).get('Site', 0)}", styles['Normal']))
    story.append(Paragraph(f"16) [CANAL] Quantidade de manifestações recebidas por Telefone: {relatorio.get('quantitativo_canais', {}).get('Telefone', 0)}", styles['Normal']))
    story.append(Paragraph(f"17) [CANAL] Quantidade de manifestações recebidas por Outros Canais: {relatorio.get('quantitativo_canais', {}).get('Outros Canais', 0)}", styles['Normal']))
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
    story.append(Paragraph(f"32) [RECLAMAÇÕES - TEMA] Quantidade de RECLAMAÇÕES sobre o tema tema SAC: {relatorio.get('reclamacoes_por_tema', {}).get('Serviço de Atendimento ao Cliente (SAC)', 0)}", styles['Normal']))
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
    story.append(Paragraph(f"46) [INDICADORES] Motivo(s) para o não cumprimento do prazo: {relatorio.get('motivo_nao_cumprimento_prazo')}", styles['Normal']))
    story.append(Paragraph(f"47) [AVALIAÇÃO-OUVIDORIA] A Ouvidoria possui avaliação de seu atendimento?: {relatorio.get('possui_avaliacao_atendimento')}", styles['Normal']))
    story.append(Paragraph(f"48) [AVALIAÇÃO-OUVIDORIA] Informar o total de respondentes: {relatorio.get('total_respondentes')}", styles['Normal']))
    story.append(Paragraph(f"49) [AVALIAÇÃO-OUVIDORIA] De uma forma geral, como o seu atendimento foi avaliado?: {relatorio.get('como_avaliacao')}", styles['Normal']))
    story.append(Paragraph(f"50) [RECOMENDAÇÕES] A Ouvidoria fez recomendações para melhoria do processo de trabalho da operadora?: {relatorio.get('fez_recomendacoes')}", styles['Normal']))
    story.append(Paragraph(f"51) [RECOMENDAÇÕES] Informar, resumidamente, as recomendações propostas.: {relatorio.get('recomendacoes_propostas')}", styles['Normal']))
    story.append(Paragraph(f"52) [RECOMENDAÇÕES] Por que a ouvidoria não fez recomendações de melhoria?:", styles['Normal']))
    story.append(Paragraph(f"53) [RECOMENDAÇÕES] Como considera o estágio de implementação das recomendações feitas em 2023?: {relatorio.get('estagio_implementacao')}", styles['Normal']))
    story.append(Paragraph(f"54) [ESTRUTURA] Quantas pessoas compõem exclusivamente a unidade de Ouvidoria?: {relatorio.get('pessoas_unidade_ouvidoria')}", styles['Normal']))
    story.append(Paragraph(f"55) [DIVULGAÇÃO] Como a operadora divulga a existência da Ouvidoria?: {relatorio.get('divulgacao_ouvidoria')}", styles['Normal']))
    story.append(Paragraph(f"56) [ACOMPANHAMENTO] A Ouvidoria acompanha o desempenho da operadora na Notificação de Intermediação Preliminar (NIP)?: {relatorio.get('acompanha_nip')}", styles['Normal']))
    story.append(Paragraph(f"57) [ACOMPANHAMENTO] A Ouvidoria tomou alguma ação para tentar reduzir a quantidade de NIPs? Se sim, descreva.: {relatorio.get('acoes_para_reduzir_nips')}", styles['Normal']))
    story.append(Paragraph(f"58) [ACOMPANHAMENTO] A Ouvidoria conhece o Índice de Desempenho da Saúde Suplementar (IDSS) da operadora e a pesquisa de satisfação junto ao consumidor que o integra?: {relatorio.get('conhece_idss_pesquisa_satisfacao')}", styles['Normal']))
    story.append(Paragraph(f"59) [ACOMPANHAMENTO] A Ouvidoria fez alguma sugestão de melhoria com base nesses documentos? Se sim, descreva.: {relatorio.get('sugestao_melhoria_documentos')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"Este documento foi gerado automaticamente pelo sistema Protocolo Eletrônico em {datetime.now().strftime('%d/%m/%Y')}.", styles['Normal']))

    doc.build(story)
    return "relatorio_rea.pdf"

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == USERNAME and password == PASSWORD:
            # Chama a função de log após um login bem-sucedido
            ip_address = request.remote_addr
            log_access(username, ip_address)
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Credenciais inválidas.")
    return render_template("login.html")

@app.route("/dashboard", methods=['GET', 'POST'])
def dashboard():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date = pd.to_datetime(start_date_str) if start_date_str else None
    end_date = pd.to_datetime(end_date_str) if end_date_str else None
    
    data = get_data_from_url()
    relatorio = process_data(data, start_date, end_date)
    
    if relatorio is None:
        return "Erro ao obter dados. Verifique sua URL e a conexão.", 500

    # Paleta de cores com base na identidade visual
    color_palette = ["#59BEAF", "#467090", "#96E5E5", "#167F7F", '#931C76', '#9B182C']
    
    # ---- Gráfico de Distribuição por Tipo de Manifestação ----
    df_tipos = pd.DataFrame(list(relatorio['quantitativo_tipos'].items()), columns=['Tipo', 'Quantidade']) if relatorio.get('quantitativo_tipos') else pd.DataFrame(columns=['Tipo', 'Quantidade'])
    fig_tipos = px.pie(
        df_tipos, 
        values='Quantidade', 
        names='Tipo', 
        title='Distribuição por Tipo de Manifestação',
        color_discrete_sequence=color_palette
    )
    fig_tipos.update_traces(
        textposition='inside', 
        textinfo='percent+label',
        marker_line_width=1,
        marker_line_color='black',
        textfont=dict(size=17) # <--- **ADICIONADO:** Aumenta o tamanho da fonte do texto na fatia do gráfico de pizza
    )
    fig_tipos.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor='#e0e5ec',
        plot_bgcolor='#e0e5ec',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            title_text='',
            font=dict(
                size=17 
            )
        )
    )
    div_tipos = fig_tipos.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
    )

    # ---- Gráfico de Distribuição por Canal de Entrada ----
    df_canais = pd.DataFrame(list(relatorio['quantitativo_canais'].items()), columns=['Canal', 'Quantidade']) if relatorio.get('quantitativo_canais') else pd.DataFrame(columns=['Canal', 'Quantidade'])
    fig_canais = px.pie(
        df_canais, 
        values='Quantidade', 
        names='Canal', 
        title='Distribuição por Canal de Entrada',
        color_discrete_sequence=color_palette
    )
    fig_canais.update_traces(
        textposition='inside', 
        textinfo='percent+label',
        marker_line_width=1,
        marker_line_color='black',
        textfont=dict(size=17) # <--- **ADICIONADO:** Aumenta o tamanho da fonte do texto na fatia do gráfico de pizza
    )
    fig_canais.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor='#e0e5ec',
        plot_bgcolor='#e0e5ec',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            title_text='',
            font=dict(
                size=17 
            )
        )
    )
    div_canais = fig_canais.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
    )

    # ---- Gráfico Quantidade por Tema de Manifestação ----
    df_temas = pd.DataFrame(list(relatorio['quantitativo_temas'].items()), columns=['Tema', 'Quantidade']) if relatorio.get('quantitativo_temas') else pd.DataFrame(columns=['Tema', 'Quantidade'])
    fig_temas = px.bar(
        df_temas, 
        x='Tema', 
        y='Quantidade', 
        title='Quantidade por Tema de Manifestação',
        color_discrete_sequence=color_palette
    )
    fig_temas.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_title="",
        yaxis_title="Quantidade",
        paper_bgcolor='#e0e5ec',
        plot_bgcolor='#e0e5ec',
        xaxis=dict(
            tickfont=dict(size=17), # <--- **ADICIONADO:** Aumenta o tamanho da fonte dos rótulos do eixo X
            title_font=dict(size=17) # <--- Opcional: Aumenta o tamanho da fonte do título do eixo X, se houver
        ),
        yaxis=dict(
            tickfont=dict(size=17), # <--- **ADICIONADO:** Aumenta o tamanho da fonte dos rótulos do eixo Y
            title_font=dict(size=17) # <--- Opcional: Aumenta o tamanho da fonte do título do eixo Y, se houver
        )
    )
    div_temas = fig_temas.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
    )
    
    # ---- Gráfico Quantidade por Vínculo do Beneficiário ----
    df_vinculo = pd.DataFrame(list(relatorio['quantitativo_vinculo_beneficiario'].items()), columns=['Vínculo', 'Quantidade']) if relatorio.get('quantitativo_vinculo_beneficiario') else pd.DataFrame(columns=['Vínculo', 'Quantidade'])
    fig_vinculo = px.bar(
        df_vinculo, 
        x='Vínculo', 
        y='Quantidade', 
        title='Quantidade por Vínculo do Beneficiário',
        color_discrete_sequence=color_palette
    )
    fig_vinculo.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_title="",
        yaxis_title="Quantidade",
        paper_bgcolor='#e0e5ec',
        plot_bgcolor='#e0e5ec',
        xaxis=dict(
            tickfont=dict(size=17), # <--- **ADICIONADO:** Aumenta o tamanho da fonte dos rótulos do eixo X
            title_font=dict(size=17) # <--- Opcional: Aumenta o tamanho da fonte do título do eixo X, se houver
        ),
        yaxis=dict(
            tickfont=dict(size=17), # <--- **ADICIONADO:** Aumenta o tamanho da fonte dos rótulos do eixo Y
            title_font=dict(size=17) # <--- Opcional: Aumenta o tamanho da fonte do título do eixo Y, se houver
        )
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
        end_date=end_date_str
    )

@app.route("/download-pdf")
def download_pdf():
    data = get_data_from_url()
    relatorio = process_data(data)
    
    if relatorio is None:
        return "Erro ao obter dados para gerar o PDF.", 500
        
    pdf_path = generate_pdf_report(relatorio)
    return send_file(pdf_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)