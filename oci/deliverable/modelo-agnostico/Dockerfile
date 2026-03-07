FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Teste rapido: escorar dados de exemplo
CMD ["python", "scoring.py", "--dados", "dados_exemplo.csv", "--modelo", "modelos/lgbm_oci_20260217_214614.pkl"]
