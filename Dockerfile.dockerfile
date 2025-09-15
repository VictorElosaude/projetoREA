# Use uma imagem oficial do Python como base
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o arquivo de dependências e as instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todos os arquivos do projeto para o container
COPY . .

# Expose a porta que o Flask vai rodar
EXPOSE 5000

# Comando para iniciar a aplicação usando Gunicorn
# Isso permite que a aplicação seja executada de forma robusta em produção
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]