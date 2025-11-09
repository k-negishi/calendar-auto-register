#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SAM_CONFIG_FILE=${SAM_CONFIG_FILE:-"${REPO_ROOT}/infra/sam/samconfig.toml"}
SAM_CONFIG_ENV=${SAM_CONFIG_ENV:-default}
ENV_FILE=${ENV_FILE:-"${REPO_ROOT}/.env.deploy"}
BUILD_ROOT=${BUILD_ROOT:-"$(mktemp -d "${TMPDIR:-/tmp}/sam-build-XXXXXX")"}

echo ">>> Starting SAM deployment at $(date +%s%3N)"

if [[ -f "${ENV_FILE}" ]]; then
  echo ">>> Loading environment from ${ENV_FILE}"
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
else
  echo ">>> ${ENV_FILE} not found. Using existing environment variables."
fi

cd "${REPO_ROOT}"

AWS_REGION=${AWS_REGION:-ap-northeast-1}
STACK_NAME=${STACK_NAME:-calendar-auto-register}
PROJECT_NAME=${PROJECT_NAME:-calendar-auto-register}
ECR_IMAGE_REPOSITORY=${ECR_IMAGE_REPOSITORY:-}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}
SSM_DOTENV_PARAMETER=${SSM_DOTENV_PARAMETER:-/calendar-auto-register/dotenv}
S3_RAW_MAIL_BUCKET=${S3_RAW_MAIL_BUCKET:-calendar-auto-register}

if [[ -z "${ECR_IMAGE_REPOSITORY}" ]]; then
  echo "ECR_IMAGE_REPOSITORY is required (e.g., 123456789012.dkr.ecr.${AWS_REGION}.amazonaws.com/calendar-auto-register)"
  exit 1
fi

PARAM_OVERRIDES=(
  "ProjectName=${PROJECT_NAME}"
  "ImageTag=${IMAGE_TAG}"
  "SsmDotenvParameter=${SSM_DOTENV_PARAMETER}"
  "S3RawMailBucketName=${S3_RAW_MAIL_BUCKET}"
)

echo ">>> sam build (config: ${SAM_CONFIG_FILE}, env: ${SAM_CONFIG_ENV})"
sam build \
  --build-dir "${BUILD_ROOT}/.aws-sam/build" \
  --cache-dir "${BUILD_ROOT}/.aws-sam/cache" \
  --config-file "${SAM_CONFIG_FILE}" \
  --config-env "${SAM_CONFIG_ENV}" \
  --use-container \
  --parameter-overrides "${PARAM_OVERRIDES[@]}" \
  "$@"

echo ">>> copying build artifacts into repo .aws-sam directory"
rm -rf "${REPO_ROOT}/.aws-sam"
mkdir -p "${REPO_ROOT}/.aws-sam"
cp -R "${BUILD_ROOT}/.aws-sam/." "${REPO_ROOT}/.aws-sam/"

echo ">>> sam deploy"
sam deploy \
  --config-file "${SAM_CONFIG_FILE}" \
  --config-env "${SAM_CONFIG_ENV}" \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}" \
  --image-repositories "CalendarFunction=${ECR_IMAGE_REPOSITORY}" \
  --parameter-overrides "${PARAM_OVERRIDES[@]}" \
  "$@"
