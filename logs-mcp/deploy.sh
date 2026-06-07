#!/bin/bash
set -e

# Configuration variables (Override by setting env variables or editing here)
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
SERVICE_NAME="storage-monitoring-mcp"
REGION="us-central1"

# Check if project ID is available
if [ -z "$PROJECT_ID" ]; then
  echo "❌ Error: No GCP project active in gcloud config."
  echo "Please set one using: gcloud config set project <your-project-id>"
  exit 1
fi

echo "=========================================================="
echo "🚀 Deploying MCP Server to Google Cloud Run"
echo "=========================================================="
echo "🔹 Project ID:  $PROJECT_ID"
echo "🔹 Service:     $SERVICE_NAME"
echo "🔹 Region:      $REGION"
echo "=========================================================="

# Build the container using Cloud Builds and deploy to Cloud Run
echo "📦 Step 1/2: Building and pushing container image..."
IMAGE_URI="gcr.io/$PROJECT_ID/$SERVICE_NAME:latest"

gcloud builds submit --tag "$IMAGE_URI" .

echo "🚀 Step 2/2: Deploying container to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE_URI" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080

# Retrieve and print the URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$REGION" --format 'value(status.url)' 2>/dev/null)

echo "=========================================================="
echo "✅ Deployment Successful!"
echo "🔹 Cloud Run Service URL: $SERVICE_URL"
echo "🔹 SSE Endpoint Path:     $SERVICE_URL/mcp/sse"
echo "=========================================================="
echo "💡 To configure your MCP client (e.g. Claude Desktop) with this SSE endpoint, use:"
echo "{"
echo "  \"mcpServers\": {"
echo "    \"storage-monitoring\": {"
echo "      \"url\": \"$SERVICE_URL/mcp/sse\""
echo "    }"
echo "  }"
echo "}"
echo "=========================================================="
