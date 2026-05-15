FROM python:3.12-slim

WORKDIR /workspace
COPY . .

CMD ["sh", "bench/run.sh"]
