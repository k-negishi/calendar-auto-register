FROM public.ecr.aws/lambda/python:3.12

ARG APP_ENV=prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/var/task/app/src" \
    APP_ENV=${APP_ENV}

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir .

CMD ["calendar_auto_register.main.lambda_handler"]
