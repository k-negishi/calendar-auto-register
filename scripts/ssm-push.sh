#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE=${ENV_FILE:-"${REPO_ROOT}/.env.deploy"}

if [[ -f "${ENV_FILE}" ]]; then
  echo ">>> Loading environment from ${ENV_FILE}"
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
else
  echo ">>> ${ENV_FILE} not found. Using existing environment variables."
fi

AWS_REGION=${AWS_REGION:-ap-northeast-1}
SSM_DOTENV_PARAMETER=${SSM_DOTENV_PARAMETER:-/calendar-auto-register/dotenv}

ENV_PROD_FILE="${REPO_ROOT}/.env.prod"
if [[ ! -f "${ENV_PROD_FILE}" ]]; then
  echo "ERROR: ${ENV_PROD_FILE} not found"
  exit 1
fi

echo ">>> Uploading ${ENV_PROD_FILE} to SSM Parameter Store (${SSM_DOTENV_PARAMETER})"
aws ssm put-parameter \
  --name "${SSM_DOTENV_PARAMETER}" \
  --type SecureString \
  --value "$(cat "${ENV_PROD_FILE}")" \
  --overwrite \
  --region "${AWS_REGION}"

echo ">>> SSM parameter update completed successfully"
