FROM python:3.12-slim
COPY speedtest.py /speedtest.py
USER nobody
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
CMD ["python", "/speedtest.py"]
