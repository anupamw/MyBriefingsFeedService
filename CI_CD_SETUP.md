# CI/CD Pipeline Setup for Football Transfers App

This guide explains how to set up and use the automated CI/CD pipeline that deploys your FastAPI app to k3s on your DigitalOcean droplet.

## 🚀 Overview

The CI/CD pipeline automatically:
1. **Tests** your code changes
2. **Builds** a Docker image for x86_64 architecture
3. **Deploys** to k3s on your droplet
4. **Verifies** the deployment with health checks
5. **Runs** integration tests

## 📋 Prerequisites

- GitHub repository with your code
- DigitalOcean droplet with k3s installed
- SSH access to your droplet
- Docker installed locally (for testing)

## 🔧 Setup Steps

### 1. GitHub Repository Secrets

Add these secrets to your GitHub repository:

1. Go to your repository → Settings → Secrets and variables → Actions
2. Add the following secrets:

```
DROPLET_IP: Your droplet's IP address (e.g., 64.227.134.87)
SSH_PRIVATE_KEY: Your private SSH key content (the entire key, including BEGIN and END lines)
```

### 2. SSH Key Setup

Make sure your SSH key is properly set up:

```bash
# Generate SSH key if you don't have one
ssh-keygen -t rsa -b 4096 -C "your-email@example.com"

# Copy public key to droplet
ssh-copy-id root@YOUR_DROPLET_IP

# Test SSH connection
ssh root@YOUR_DROPLET_IP "echo 'SSH connection successful'"
```

### 3. Verify k3s Installation

Ensure k3s is running on your droplet:

```bash
ssh root@YOUR_DROPLET_IP
sudo systemctl status k3s
sudo kubectl get nodes
```

## 🔄 How the Pipeline Works

### Trigger
- **Push to main/master branch**: Triggers full deployment
- **Pull Request**: Runs tests only (no deployment)

### Pipeline Stages

1. **Test Job**
   - Installs Python dependencies
   - Runs application tests
   - Tests Docker build

2. **Build and Deploy Job** (only on main/master)
   - Builds Docker image for x86_64
   - Saves image as tar file
   - Copies image and manifests to droplet
   - Deploys to k3s
   - Runs health checks and integration tests

## 🧪 Testing Locally

You can test the deployment process locally using the provided script:

```bash
# Make sure you have the right environment variables
export DROPLET_IP="64.227.134.87"  # Your droplet IP
export SSH_KEY_PATH="~/.ssh/id_rsa"  # Path to your SSH key

# Run the deployment script
./scripts/deploy.sh
```

## 📁 File Structure

```
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions workflow
├── k8s/
│   ├── namespace.yaml          # Kubernetes namespace
│   ├── deployment.yaml         # App deployment
│   └── service.yaml           # Service configuration
├── scripts/
│   └── deploy.sh              # Local deployment script
├── test_app.py                # Integration tests
└── CI_CD_SETUP.md            # This file
```

## 🔍 Monitoring and Debugging

### Check Pipeline Status
- Go to your GitHub repository → Actions tab
- View the latest workflow run

### Check Deployment Status
```bash
ssh root@YOUR_DROPLET_IP

# Check pod status
sudo kubectl get pods -n football-transfers

# Check service status
sudo kubectl get svc -n football-transfers

# View pod logs
sudo kubectl logs -n football-transfers -l app=football-transfers-app

# Check deployment events
sudo kubectl describe deployment football-transfers-app -n football-transfers
```

### Common Issues

1. **SSH Connection Failed**
   - Verify SSH key is correct in GitHub secrets
   - Check droplet IP address
   - Ensure SSH key is added to droplet

2. **Image Pull Error**
   - Check if image was built for correct architecture (x86_64)
   - Verify image was saved and copied correctly

3. **Pod Not Ready**
   - Check pod logs: `sudo kubectl logs -n football-transfers <pod-name>`
   - Verify health checks are passing
   - Check resource limits

## 🚀 Making Changes

### Code Changes
1. Make your changes locally
2. Test with: `python test_app.py http://localhost:8000`
3. Commit and push to main branch
4. Pipeline will automatically deploy

### Configuration Changes
- Update Kubernetes manifests in `k8s/` directory
- Push changes to trigger deployment
- Pipeline will apply new configuration

### Environment Variables
- Add environment variables to `k8s/deployment.yaml`
- Push changes to deploy

## 🔒 Security Considerations

- SSH keys are stored as GitHub secrets (encrypted)
- Images are built locally and transferred securely
- No external registries required
- k3s runs with minimal privileges

## 📊 Performance

- Build time: ~2-3 minutes
- Deployment time: ~1-2 minutes
- Total pipeline time: ~5-7 minutes

## 🆘 Troubleshooting

### Pipeline Fails
1. Check GitHub Actions logs
2. Verify secrets are correct
3. Test SSH connection manually
4. Check droplet resources

### App Not Responding
1. Check pod status: `sudo kubectl get pods -n football-transfers`
2. View logs: `sudo kubectl logs -n football-transfers <pod-name>`
3. Test health endpoint: `curl http://YOUR_DROPLET_IP:30080/health`
4. Check service: `sudo kubectl get svc -n football-transfers`

### Rollback
If deployment fails, you can rollback:

```bash
ssh root@YOUR_DROPLET_IP
sudo kubectl rollout undo deployment/football-transfers-app -n football-transfers
```

## 🎉 Success!

Once everything is set up, every push to your main branch will automatically deploy your changes to production! 🚀 