FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && guestgraph demo --data /app/data --out /app/out
ENV GUESTGRAPH_DATA=/app/data
EXPOSE 8000
CMD ["uvicorn", "guestgraph.api:app", "--host", "0.0.0.0", "--port", "8000"]
