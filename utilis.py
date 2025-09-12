import pandas as pd

def process_data(data):
    """
    Processa os dados brutos e os transforma em um DataFrame.
    Calcula todas as métricas necessárias para o formulário REA.
    """
    df = pd.DataFrame(data)
    
    # Exemplo de cálculo: Contagem de manifestações por tipo
    df_tipos = df['*Tipo da Manifestação'].value_counts().reset_index()
    df_tipos.columns = ['Tipo', 'Quantidade']
    
    return {
        'df_tipos': df_tipos,
        # Adicionar mais dataframes e métricas aqui
    }

def generate_report(processed_data):
    """
    Gera os gráficos e o arquivo PDF.
    """
    # A lógica para gerar os gráficos e o PDF virá aqui
    pass