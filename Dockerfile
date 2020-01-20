FROM python:alpine

COPY showmail.py ./

CMD ["python3", "showmail.py", "-d", "/mail"]
