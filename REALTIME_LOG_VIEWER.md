# Real-Time Log Viewer

A simple web-based log viewer that shows Docker container logs in real-time as they happen.

## 🚀 Quick Start

### Deploy on your droplet:

```bash
# SSH into your droplet
ssh root@YOUR_DROPLET_IP

# Download and run the deployment script
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/realtime-log-viewer.sh
chmod +x realtime-log-viewer.sh
sudo ./realtime-log-viewer.sh
```

### Access the web interface:

```
http://YOUR_DROPLET_IP:8080
```

## 🔴 Features

- **Real-time streaming** - logs appear as they happen
- **Live statistics** - total logs, errors, warnings
- **Color-coded levels** - errors (red), warnings (yellow), info (green)
- **All containers** - automatically monitors all Docker containers
- **Web interface** - view logs in your browser
- **Auto-scroll** - automatically shows latest logs

## 📊 Usage

1. Open `http://YOUR_DROPLET_IP:8080` in your browser
2. Click **"Start Streaming"** to begin
3. Watch logs appear in real-time!
4. Use **"Stop Streaming"** to pause

## 🛠️ Management

```bash
# Start the service
systemctl start realtime-log-viewer

# Stop the service
systemctl stop realtime-log-viewer

# Check status
systemctl status realtime-log-viewer

# View service logs
journalctl -u realtime-log-viewer -f
```

## 🎯 Why This Solution?

- ✅ **Zero code changes** - works with existing containers
- ✅ **Real-time** - logs appear as they happen
- ✅ **Simple setup** - single script deployment
- ✅ **Lightweight** - minimal resource usage
- ✅ **Web interface** - easy to use from anywhere

## 🔧 How It Works

1. Uses `docker logs -f` to follow all container logs
2. Streams logs via Server-Sent Events to your browser
3. Parses timestamps and log levels automatically
4. Shows live statistics and color-coded output

## 📝 Troubleshooting

### Service not starting:
```bash
systemctl status realtime-log-viewer
journalctl -u realtime-log-viewer -f
```

### No logs appearing:
```bash
# Check if containers are running
docker ps

# Check if service can access Docker
docker logs $(docker ps -q | head -1)
```

### Web interface not accessible:
```bash
# Check if service is running
systemctl status realtime-log-viewer

# Check firewall
sudo ufw status
```

## 🎉 That's it!

No complex ELK stacks, no Loki setup, no code changes needed. Just a simple web interface that shows your logs in real-time. 