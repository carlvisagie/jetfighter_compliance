FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ARG KYC_GIT_COMMIT=unknown
ENV KYC_GIT_COMMIT=${KYC_GIT_COMMIT}

ENV PORT=10000

EXPOSE 10000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000", "--timeout-keep-alive", "120", "--limit-concurrency", "80"]
