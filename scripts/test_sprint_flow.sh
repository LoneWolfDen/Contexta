#!/bin/bash

echo "----- STARTING CONTEXTA API TEST -----"

BASE_URL="http://localhost:5000"

# Helper function (safe JSON parsing)
parse_json_field() {
  echo "$1" | python3 -c "import sys, json; print(json.load(sys.stdin).get('$2', ''))" 2>/dev/null
}

# --- STEP 1: Create project ---
echo "Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST $BASE_URL/projects \
-H "Content-Type: application/json" \
-d '{"name": "Auto_Test_Project"}')

PROJECT_ID=$(parse_json_field "$PROJECT_RESPONSE" "project_id")

if [ -z "$PROJECT_ID" ]; then
  echo "❌ Project creation failed"; echo "$PROJECT_RESPONSE"; exit 1
fi

echo "✅ Project ID: $PROJECT_ID"

# --- STEP 2: Create artifacts ---
echo "Creating artifacts..."

ART1_RESPONSE=$(curl -s -X POST $BASE_URL/artifacts \
-H "Content-Type: application/json" \
-d "{
  \"project_id\": \"$PROJECT_ID\",
  \"type\": \"document\",
  \"source_type\": \"upload\",
  \"file_path\": \"/files/sow.txt\"
}")

ART1_ID=$(parse_json_field "$ART1_RESPONSE" "artifact_id")

ART2_RESPONSE=$(curl -s -X POST $BASE_URL/artifacts \
-H "Content-Type: application/json" \
-d "{
  \"project_id\": \"$PROJECT_ID\",
  \"type\": \"document\",
  \"source_type\": \"upload\",
  \"file_path\": \"/files/architecture.txt\"
}")

ART2_ID=$(parse_json_field "$ART2_RESPONSE" "artifact_id")

echo "✅ Artifacts: $ART1_ID , $ART2_ID"

# --- STEP 3: Create version ---
echo "Creating version..."

VERSION_RESPONSE=$(curl -s -X POST $BASE_URL/versions \
-H "Content-Type: application/json" \
-d "{
  \"project_id\": \"$PROJECT_ID\",
  \"artifact_ids\": [\"$ART1_ID\", \"$ART2_ID\"]
}")

VERSION_ID=$(parse_json_field "$VERSION_RESPONSE" "version_id")

if [ -z "$VERSION_ID" ]; then
  echo "❌ Version creation failed"; echo "$VERSION_RESPONSE"; exit 1
fi

echo "✅ Version ID: $VERSION_ID"

# --- STEP 4: Create base review ---
echo "Creating base review..."

REVIEW1=$(curl -s -X POST $BASE_URL/reviews \
-H "Content-Type: application/json" \
-d "{
  \"version_id\": \"$VERSION_ID\"
}")

REVIEW1_ID=$(parse_json_field "$REVIEW1" "review_id")

echo "✅ Review1 ID: $REVIEW1_ID"

# --- STEP 5: Create persona review ---
echo "Creating persona-based review..."

REVIEW2=$(curl -s -X POST $BASE_URL/reviews \
-H "Content-Type: application/json" \
-d "{
  \"version_id\": \"$VERSION_ID\",
  \"personas\": [\"Architect\", \"Security\"],
  \"user_context\": \"Focus on architecture and security risks\"
}")

REVIEW2_ID=$(parse_json_field "$REVIEW2" "review_id")

echo "✅ Review2 ID: $REVIEW2_ID"

# --- STEP 6: Reconciliation ---
echo "Running reconciliation..."

RECON_RESPONSE=$(curl -s -X POST $BASE_URL/reconciliation \
-H "Content-Type: application/json" \
-d "{
  \"review_ids\": [\"$REVIEW1_ID\", \"$REVIEW2_ID\"]
}")

echo "----- RECONCILIATION OUTPUT -----"
echo "$RECON_RESPONSE" | python3 -m json.tool

echo "----- TEST COMPLETE ✅ -----"