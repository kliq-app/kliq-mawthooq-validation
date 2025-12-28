#!/bin/bash

# GCP Cloud Run Deployment Script for Mawthooq Validator
# This script deploys the license extractor service to Cloud Run

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"kliq-431715"}
REGION=${GCP_REGION:-"me-central2"}
SERVICE_NAME="mawthooq-validator"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
DOMAIN_NAME=${DOMAIN_NAME:-"mawthooq.kliqapp.io"}

# Load Balancer components
NEG_NAME="${SERVICE_NAME}-neg"
BACKEND_SERVICE_NAME="${SERVICE_NAME}-backend"
URL_MAP_NAME="${SERVICE_NAME}-url-map"
SSL_CERT_NAME="${SERVICE_NAME}-cert"
HTTPS_PROXY_NAME="${SERVICE_NAME}-https-proxy"
HTTP_PROXY_NAME="${SERVICE_NAME}-http-proxy"
FORWARDING_RULE_NAME="${SERVICE_NAME}-lb"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   Mawthooq Validator Deployment${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}Project:${NC} ${PROJECT_ID}"
echo -e "${GREEN}Region:${NC} ${REGION}"
echo -e "${GREEN}Domain:${NC} ${DOMAIN_NAME}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Set the project
echo -e "${YELLOW}Setting GCP project...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com compute.googleapis.com certificatemanager.googleapis.com

# Build the Docker image using Cloud Build
echo -e "${YELLOW}Building Docker image...${NC}"
gcloud builds submit --tag ${IMAGE_NAME}:latest .

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Docker build failed${NC}"
    exit 1
fi

# Load environment variables from .env files
echo -e "${YELLOW}Loading configuration...${NC}"

# Try .env.production first, then .env
if [ -f ".env.production" ]; then
    echo -e "${YELLOW}Loading from .env.production...${NC}"
    set -a
    source .env.production
    set +a
elif [ -f ".env" ]; then
    echo -e "${YELLOW}Loading from .env...${NC}"
    set -a
    source .env
    set +a
fi

# Check if API_KEYS is set (required for production)
if [ -z "${API_KEYS}" ]; then
    echo -e "${YELLOW}Warning: API_KEYS not set. Service will run without authentication.${NC}"
    echo "Set API_KEYS in .env.production for production deployments."
fi

# Build environment variables string
ENV_VARS="APP_ENV=production"
ENV_VARS="${ENV_VARS},LOG_LEVEL=${LOG_LEVEL:-INFO}"
ENV_VARS="${ENV_VARS},MAX_DOWNLOAD_MB=${MAX_DOWNLOAD_MB:-25}"
ENV_VARS="${ENV_VARS},REQUEST_TIMEOUT_SEC=${REQUEST_TIMEOUT_SEC:-20}"
ENV_VARS="${ENV_VARS},RATE_LIMIT_PER_MIN=${RATE_LIMIT_PER_MIN:-60}"
ENV_VARS="${ENV_VARS},METRICS_ENABLED=${METRICS_ENABLED:-true}"
ENV_VARS="${ENV_VARS},OCR_ENABLED=${OCR_ENABLED:-true}"
ENV_VARS="${ENV_VARS},OCR_LANGUAGE=${OCR_LANGUAGE:-ara+eng}"
ENV_VARS="${ENV_VARS},MAX_OCR_PAGES=${MAX_OCR_PAGES:-2}"
ENV_VARS="${ENV_VARS},MIN_ARABIC_RATIO=${MIN_ARABIC_RATIO:-0.05}"
ENV_VARS="${ENV_VARS},MIN_TEXT_LENGTH=${MIN_TEXT_LENGTH:-50}"
ENV_VARS="${ENV_VARS},GCAM_LOOKUP_ENABLED=${GCAM_LOOKUP_ENABLED:-true}"
ENV_VARS="${ENV_VARS},GCAM_BASE_URL=${GCAM_BASE_URL:-https://elaam.gmedia.gov.sa}"
ENV_VARS="${ENV_VARS},GCAM_LOOKUP_TIMEOUT_SEC=${GCAM_LOOKUP_TIMEOUT_SEC:-15}"
ENV_VARS="${ENV_VARS},GCAM_LOOKUP_RETRY_COUNT=${GCAM_LOOKUP_RETRY_COUNT:-2}"
ENV_VARS="${ENV_VARS},GCAM_CB_FAILURE_THRESHOLD=${GCAM_CB_FAILURE_THRESHOLD:-5}"
ENV_VARS="${ENV_VARS},GCAM_CB_RESET_SEC=${GCAM_CB_RESET_SEC:-60}"

# Add API_KEYS if set
if [ -n "${API_KEYS}" ]; then
    ENV_VARS="${ENV_VARS},API_KEYS=${API_KEYS}"
fi

# Add ALLOWED_DOMAINS if set
if [ -n "${ALLOWED_DOMAINS}" ]; then
    ENV_VARS="${ENV_VARS},ALLOWED_DOMAINS=${ALLOWED_DOMAINS}"
fi

# Add REDIS_URL if set
if [ -n "${REDIS_URL}" ]; then
    ENV_VARS="${ENV_VARS},REDIS_URL=${REDIS_URL}"
    echo -e "${GREEN}Redis URL configured for distributed rate limiting${NC}"
fi

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"

gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:latest \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --set-env-vars="${ENV_VARS}" \
    --memory 2Gi \
    --cpu 2 \
    --timeout 60 \
    --concurrency 80 \
    --max-instances 10 \
    --min-instances 0

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Deployment failed${NC}"
    exit 1
fi

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')
echo -e "${GREEN}Cloud Run URL: ${SERVICE_URL}${NC}"

# ==========================================
# Setup Custom Domain with Load Balancer
# ==========================================
echo ""
echo -e "${YELLOW}Setting up custom domain: ${DOMAIN_NAME}${NC}"

# Reserve static IP address
echo -e "${YELLOW}Reserving static IP...${NC}"
if ! gcloud compute addresses describe ${SERVICE_NAME}-ip --global &>/dev/null; then
    gcloud compute addresses create ${SERVICE_NAME}-ip \
        --global \
        --ip-version=IPV4
    echo -e "${GREEN}Static IP reserved${NC}"
else
    echo -e "${GREEN}Static IP already exists${NC}"
fi

STATIC_IP=$(gcloud compute addresses describe ${SERVICE_NAME}-ip --global --format="value(address)")
echo -e "${GREEN}Static IP: ${STATIC_IP}${NC}"

# Create NEG (Network Endpoint Group) for Cloud Run
echo -e "${YELLOW}Creating Network Endpoint Group...${NC}"
if ! gcloud compute network-endpoint-groups describe ${NEG_NAME} --region=${REGION} &>/dev/null; then
    gcloud compute network-endpoint-groups create ${NEG_NAME} \
        --region=${REGION} \
        --network-endpoint-type=serverless \
        --cloud-run-service=${SERVICE_NAME}
    echo -e "${GREEN}NEG created${NC}"
else
    echo -e "${GREEN}NEG already exists${NC}"
fi

# Create backend service
echo -e "${YELLOW}Creating backend service...${NC}"
if ! gcloud compute backend-services describe ${BACKEND_SERVICE_NAME} --global &>/dev/null; then
    gcloud compute backend-services create ${BACKEND_SERVICE_NAME} \
        --global \
        --load-balancing-scheme=EXTERNAL \
        --protocol=HTTP

    # Add NEG to backend service
    gcloud compute backend-services add-backend ${BACKEND_SERVICE_NAME} \
        --global \
        --network-endpoint-group=${NEG_NAME} \
        --network-endpoint-group-region=${REGION}

    echo -e "${GREEN}Backend service created${NC}"
else
    echo -e "${GREEN}Backend service already exists${NC}"
fi

# Create URL map
echo -e "${YELLOW}Creating URL map...${NC}"
if ! gcloud compute url-maps describe ${URL_MAP_NAME} --global &>/dev/null; then
    gcloud compute url-maps create ${URL_MAP_NAME} \
        --default-service=${BACKEND_SERVICE_NAME} \
        --global
    echo -e "${GREEN}URL map created${NC}"
else
    echo -e "${GREEN}URL map already exists${NC}"
fi

# Create SSL certificate (managed by Google)
echo -e "${YELLOW}Setting up SSL certificate for ${DOMAIN_NAME}...${NC}"
if ! gcloud compute ssl-certificates describe ${SSL_CERT_NAME} --global &>/dev/null; then
    gcloud compute ssl-certificates create ${SSL_CERT_NAME} \
        --domains=${DOMAIN_NAME} \
        --global
    echo -e "${GREEN}SSL certificate created for ${DOMAIN_NAME}${NC}"
else
    echo -e "${GREEN}SSL certificate already exists${NC}"
fi

# Create HTTPS proxy
echo -e "${YELLOW}Creating HTTPS proxy...${NC}"
if ! gcloud compute target-https-proxies describe ${HTTPS_PROXY_NAME} --global &>/dev/null; then
    gcloud compute target-https-proxies create ${HTTPS_PROXY_NAME} \
        --ssl-certificates=${SSL_CERT_NAME} \
        --url-map=${URL_MAP_NAME} \
        --global
    echo -e "${GREEN}HTTPS proxy created${NC}"
else
    echo -e "${GREEN}HTTPS proxy already exists${NC}"
fi

# Create forwarding rule for HTTPS
echo -e "${YELLOW}Creating HTTPS forwarding rule...${NC}"
if ! gcloud compute forwarding-rules describe ${FORWARDING_RULE_NAME}-https --global &>/dev/null; then
    gcloud compute forwarding-rules create ${FORWARDING_RULE_NAME}-https \
        --address=${SERVICE_NAME}-ip \
        --target-https-proxy=${HTTPS_PROXY_NAME} \
        --global \
        --ports=443
    echo -e "${GREEN}HTTPS forwarding rule created${NC}"
else
    echo -e "${GREEN}HTTPS forwarding rule already exists${NC}"
fi

# Create HTTP proxy (for redirect to HTTPS)
echo -e "${YELLOW}Creating HTTP proxy...${NC}"
if ! gcloud compute target-http-proxies describe ${HTTP_PROXY_NAME} --global &>/dev/null; then
    gcloud compute target-http-proxies create ${HTTP_PROXY_NAME} \
        --url-map=${URL_MAP_NAME} \
        --global
    echo -e "${GREEN}HTTP proxy created${NC}"
else
    echo -e "${GREEN}HTTP proxy already exists${NC}"
fi

# Create forwarding rule for HTTP
echo -e "${YELLOW}Creating HTTP forwarding rule...${NC}"
if ! gcloud compute forwarding-rules describe ${FORWARDING_RULE_NAME}-http --global &>/dev/null; then
    gcloud compute forwarding-rules create ${FORWARDING_RULE_NAME}-http \
        --address=${SERVICE_NAME}-ip \
        --target-http-proxy=${HTTP_PROXY_NAME} \
        --global \
        --ports=80
    echo -e "${GREEN}HTTP forwarding rule created${NC}"
else
    echo -e "${GREEN}HTTP forwarding rule already exists${NC}"
fi

# ==========================================
# Summary
# ==========================================
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   Deployment Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}Access URLs:${NC}"
echo -e "  Cloud Run: ${BLUE}${SERVICE_URL}${NC}"
echo -e "  Static IP: ${BLUE}http://${STATIC_IP}${NC}"
echo -e "  Custom Domain: ${BLUE}https://${DOMAIN_NAME}${NC}"
echo ""
echo -e "${GREEN}Configuration Status:${NC}"
if [ -n "${API_KEYS}" ]; then
    echo "  API Authentication: Enabled"
else
    echo "  API Authentication: Disabled (open access)"
fi
if [ -n "${REDIS_URL}" ]; then
    echo "  Rate Limiting: Redis-backed (distributed)"
else
    echo "  Rate Limiting: In-memory (single instance)"
fi
echo "  OCR: ${OCR_ENABLED:-true}"
echo "  GCAM Lookup: ${GCAM_LOOKUP_ENABLED:-true}"
echo "  Metrics: ${METRICS_ENABLED:-true}"
echo ""
echo -e "${GREEN}DNS Configuration Required:${NC}"
echo -e "  Add an A record: ${YELLOW}${DOMAIN_NAME} -> ${STATIC_IP}${NC}"
echo ""
echo -e "${GREEN}Test your API:${NC}"
echo -e "${YELLOW}curl -s https://${DOMAIN_NAME}/health${NC}"
echo ""
if [ -n "${API_KEYS}" ]; then
    FIRST_KEY=$(echo ${API_KEYS} | cut -d',' -f1)
    echo -e "${YELLOW}curl -X POST https://${DOMAIN_NAME}/v1/extract \\
  -H 'Content-Type: application/json' \\
  -H 'X-API-Key: ${FIRST_KEY}' \\
  -d '{\"source_url\":\"https://example.com/document.pdf\",\"doc_type_hint\":\"auto\"}'${NC}"
fi
echo ""
echo -e "${YELLOW}Note: SSL certificate provisioning may take 15-60 minutes after DNS is configured.${NC}"
echo -e "${YELLOW}Load balancer propagation may take 5-10 minutes.${NC}"
echo ""
echo -e "${GREEN}Monitoring:${NC}"
echo "1. Logs: gcloud logging read --project=${PROJECT_ID} 'resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}'"
echo "2. Metrics: https://console.cloud.google.com/run/detail/${REGION}/${SERVICE_NAME}/metrics?project=${PROJECT_ID}"
echo "3. SSL Status: gcloud compute ssl-certificates describe ${SSL_CERT_NAME} --global --format='value(managed.status)'"
