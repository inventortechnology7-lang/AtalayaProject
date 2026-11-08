FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home edge && mkdir /data && chown edge /data
COPY *.py ./
USER 10001:10001
ENV DB_RUTA=/data/katana.db ORDENES_SOCK=/data/ordenes.sock ORDENES_DIR=/data AUTH_DB=/data/usuarios.db
EXPOSE 8300
CMD ["python", "-u", "run.py"]
