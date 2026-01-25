# IAM Permissions Setup Guide

This guide explains the IAM permissions needed for deploying and running Cloud Functions with Cloud Build.

## Required Permissions

### 1. Cloud Build Service Account (for deployment)

**Service Account**: `1052858128591@cloudbuild.gserviceaccount.com`

**Required Roles**:
- `roles/cloudfunctions.developer` - Deploy and manage Cloud Functions
- `roles/iam.serviceAccountUser` - Use service accounts for function execution
- `roles/storage.admin` - Access storage buckets (or more specific bucket permissions)

**How to Grant** (requires Project Owner/Editor):
```bash
PROJECT_NUMBER=1052858128591
gcloud projects add-iam-policy-binding lightrun-temp \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding lightrun-temp \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding lightrun-temp \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/storage.admin"
```

**Or via GCP Console**:
1. Go to: IAM & Admin > IAM
2. Find: `1052858128591@cloudbuild.gserviceaccount.com`
3. Click Edit (pencil icon)
4. Add roles:
   - Cloud Functions Developer
   - Service Account User
   - Storage Admin

### 2. Storage Bucket Permissions

#### Input Bucket (`lightrun-image-input`)

**For Cloud Build** (already configured):
- `roles/storage.objectCreator` - Upload objects to trigger function

**For Function Execution** (auto-configured when function is deployed):
- Function's service account needs `roles/storage.objectViewer` to read uploaded images

#### Output Bucket (`lightrun-image-output`)

**For Cloud Build** (already configured):
- `roles/storage.objectAdmin` - Full access for deployment operations

**For Function Execution** (auto-configured when function is deployed):
- Function's service account needs `roles/storage.objectCreator` to upload blurred images

### 3. Function Service Account (created automatically)

When the function is deployed, it will use a default service account:
`1052858128591-compute@developer.gserviceaccount.com`

**Required Roles** (usually auto-granted):
- `roles/storage.objectViewer` on `lightrun-image-input`
- `roles/storage.objectCreator` on `lightrun-image-output`
- `roles/vision.annotator` - For Vision API (if using Vision API)

**To grant manually** (if needed):
```bash
FUNCTION_SA="1052858128591-compute@developer.gserviceaccount.com"

# Read from input bucket
gsutil iam ch serviceAccount:${FUNCTION_SA}:roles/storage.objectViewer gs://lightrun-image-input

# Write to output bucket
gsutil iam ch serviceAccount:${FUNCTION_SA}:roles/storage.objectCreator gs://lightrun-image-output

# Vision API access
gcloud projects add-iam-policy-binding lightrun-temp \
  --member="serviceAccount:${FUNCTION_SA}" \
  --role="roles/vision.annotator"
```

## Current Status

✅ **Bucket-level permissions**: Configured for Cloud Build service account
❌ **Project-level permissions**: Need to be granted by Project Owner/Editor

## Troubleshooting

### If deployment fails with permission errors:

1. **Check Cloud Build service account permissions**:
   ```bash
   gcloud projects get-iam-policy lightrun-temp \
     --flatten="bindings[].members" \
     --filter="bindings.members:1052858128591@cloudbuild.gserviceaccount.com"
   ```

2. **Check bucket permissions**:
   ```bash
   gsutil iam get gs://lightrun-image-input
   gsutil iam get gs://lightrun-image-output
   ```

3. **Common errors**:
   - `Permission denied on service account`: Grant `roles/iam.serviceAccountUser`
   - `Permission denied on storage`: Grant storage roles
   - `Permission denied on functions`: Grant `roles/cloudfunctions.developer`

## Minimal Permissions (Least Privilege)

For better security, use more specific roles:

**Cloud Build Service Account**:
- `roles/cloudfunctions.developer` - Deploy functions
- `roles/iam.serviceAccountUser` - Use service accounts
- `roles/storage.objectCreator` on input bucket (bucket-level, not project-level)
- `roles/storage.objectAdmin` on output bucket (bucket-level, not project-level)

**Function Service Account**:
- `roles/storage.objectViewer` on input bucket
- `roles/storage.objectCreator` on output bucket
- `roles/vision.annotator` (project-level for Vision API)
