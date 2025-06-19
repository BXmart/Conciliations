FROM python:3.11-slim

# Evitamos pegarlo todo como root
ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
# En producción, .env, se inyecta con secrets, no con copy
COPY .env .env        

EXPOSE 8081

CMD ["streamlit", "run", "app/main.py", "--server.port=8081", "--server.address=0.0.0.0"]
