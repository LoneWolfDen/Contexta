#!/bin/bash

echo "----- STARTING CONTEXTA API TEST -----"

BASE_URL="http://localhost:5000"

# Step 1: Create project
echo "Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST $BASE_URL/projects \
-H "Content-Type: application/json" \
-d '{"name": "Auto_Test_Project"}')

PROJECT_ID=$(echo $PROJECT_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['project_id'])")

echo "Project ID: $PROJECT_ID"

# Step 2: Create artifacts
echo "Creating artifacts..."

ART1_RESPONSE=$(curl -s -X POST $BASE_URL/artifacts \
-H "Content-Type: application/json" \
-d "{
  \"project_id\": \"$PROJECT_ID\",
  \"type\": \"document\",
  \"source_type\": \"upload\",
  \"file_path\": \"/files/sow.txt\"
}")

ART1_ID=$(echo $ART1_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['artifact_id'])")

ART2_RESPONSE=$(curl -s -X POST $BASE_URL/artifacts \
-H "Content-Type: application/json" \
-d "{
  \"project_id\": \"$PROJECT_ID\",
  \"type\": \"document\",
  \"source_type\": \"upload\",
  \"file_path\": \"/files/architecture.txt\"
}")

ART2_ID=$(echo $ART2_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['artifact_id'])")

echo "Artifacts: $ART1_ID , $ART2_ID"

# Step 3: Create version
echo "Creating version..."

VERSION_RESPONSE=$(curl -s -X POST $BASE_URL/versions \
-H "Content-Type: application/json" \
-d "{
  \"project_id\": \"$PROJECT_ID\",
  \"artifact_ids\": [\"$ART1_ID\", \"$ART2_ID\"]
}")

VERSION_ID=$(echo $VERSION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['version_id'])")

echo "Version ID: $VERSION_ID"

# Step 4: Create review
echo "Creating review..."

REVIEW_RESPONSE=$(curl -s -X POST $BASE_URL/reviews \
-H "Content-Type: application/json" \
-d "{
  \"version_id\": \"$VERSION_ID\"
}")

echo "----- REVIEW OUTPUT -----"
echo $REVIEW_RESPONSE | python3 -m json.tool

echo "----- TEST COMPLETE -----"
