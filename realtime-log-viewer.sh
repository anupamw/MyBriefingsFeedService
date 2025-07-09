#!/bin/bash

# Real-Time Log Viewer - Shows logs as they happen
# Uses Server-Sent Events for live streaming

set -e

echo "🚀 Starting Real-Time Log Viewer..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root or with sudo"
    exit 1
fi

# Install required packages
echo "📦 Installing required packages..."
apt update && apt install -y python3 python3-pip curl

# Create real-time log viewer
mkdir -p /opt/realtime-logs
cd /opt/realtime-logs

# Create Python web server with real-time streaming
cat > realtime_log_server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import subprocess
import json
import time
import threading
import queue
from datetime import datetime
import select
import os

# Global queue for log messages
log_queue = queue.Queue()

class RealTimeLogHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Real-Time Log Viewer</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: monospace; margin: 20px; background: #1e1e1e; color: #fff; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #333; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .controls { margin-bottom: 20px; }
        button { background: #007acc; color: white; border: none; padding: 10px 20px; margin: 5px; border-radius: 3px; cursor: pointer; }
        button:hover { background: #005a9e; }
        button.active { background: #00cc00; }
        .log-container { background: #2d2d2d; padding: 20px; border-radius: 5px; height: 600px; overflow-y: auto; }
        .log-line { margin: 2px 0; padding: 2px 5px; border-radius: 3px; }
        .log-line.error { background: #8b0000; }
        .log-line.warning { background: #8b8b00; }
        .log-line.info { background: #006400; }
        .timestamp { color: #888; }
        .container-name { color: #00ff00; font-weight: bold; }
        .message { color: #fff; }
        .status { color: #00ff00; }
        .connection-status { color: #ff6b6b; }
        .stats { background: #333; padding: 10px; border-radius: 3px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔴 Real-Time Log Viewer</h1>
            <p>Live streaming logs from all Docker containers</p>
        </div>
        
        <div class="stats" id="stats">
            <strong>📊 Stats:</strong> 
            <span id="total-logs">0</span> logs | 
            <span id="errors">0</span> errors | 
            <span id="warnings">0</span> warnings |
            <span id="containers">0</span> containers
        </div>
        
        <div class="controls">
            <button onclick="toggleStreaming()" id="stream-btn">▶️ Start Streaming</button>
            <button onclick="clearLogs()">🗑️ Clear</button>
            <button onclick="scrollToBottom()">⬇️ Scroll to Bottom</button>
            <button onclick="scrollToTop()">⬆️ Scroll to Top</button>
            <span id="connection-status" class="connection-status">Disconnected</span>
        </div>
        
        <div class="log-container" id="logs">
            <div class="log-line info">
                <span class="timestamp">[''' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ''']</span>
                <span class="container-name">SYSTEM:</span>
                <span class="message">Real-time log viewer started. Click "Start Streaming" to begin.</span>
            </div>
        </div>
    </div>

    <script>
        let eventSource = null;
        let isStreaming = false;
        let totalLogs = 0;
        let errorCount = 0;
        let warningCount = 0;
        let containers = new Set();
        
        function toggleStreaming() {
            const btn = document.getElementById('stream-btn');
            const status = document.getElementById('connection-status');
            
            if (!isStreaming) {
                // Start streaming
                eventSource = new EventSource('/stream');
                isStreaming = true;
                btn.textContent = '⏸️ Stop Streaming';
                btn.className = 'active';
                status.textContent = 'Connecting...';
                status.className = 'status';
                
                eventSource.onopen = function() {
                    status.textContent = 'Connected - Live streaming';
                    status.className = 'status';
                };
                
                eventSource.onmessage = function(event) {
                    const log = JSON.parse(event.data);
                    addLogLine(log);
                    updateStats(log);
                };
                
                eventSource.onerror = function() {
                    status.textContent = 'Connection lost - Reconnecting...';
                    status.className = 'connection-status';
                };
            } else {
                // Stop streaming
                if (eventSource) {
                    eventSource.close();
                }
                isStreaming = false;
                btn.textContent = '▶️ Start Streaming';
                btn.className = '';
                status.textContent = 'Disconnected';
                status.className = 'connection-status';
            }
        }
        
        function addLogLine(log) {
            const logsDiv = document.getElementById('logs');
            const logLine = document.createElement('div');
            logLine.className = 'log-line ' + (log.level || 'info');
            
            const timestamp = document.createElement('span');
            timestamp.className = 'timestamp';
            timestamp.textContent = '[' + log.timestamp + ']';
            
            const container = document.createElement('span');
            container.className = 'container-name';
            container.textContent = log.container + ':';
            
            const message = document.createElement('span');
            message.className = 'message';
            message.textContent = log.message;
            
            logLine.appendChild(timestamp);
            logLine.appendChild(container);
            logLine.appendChild(message);
            logsDiv.appendChild(logLine);
            
            // Auto-scroll to bottom
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
        
        function updateStats(log) {
            totalLogs++;
            containers.add(log.container);
            
            if (log.level === 'error') errorCount++;
            if (log.level === 'warning') warningCount++;
            
            document.getElementById('total-logs').textContent = totalLogs;
            document.getElementById('errors').textContent = errorCount;
            document.getElementById('warnings').textContent = warningCount;
            document.getElementById('containers').textContent = containers.size;
        }
        
        function clearLogs() {
            document.getElementById('logs').innerHTML = '';
            totalLogs = 0;
            errorCount = 0;
            warningCount = 0;
            containers.clear();
            updateStats({container: '', level: 'info'});
        }
        
        function scrollToBottom() {
            const logsDiv = document.getElementById('logs');
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
        
        function scrollToTop() {
            const logsDiv = document.getElementById('logs');
            logsDiv.scrollTop = 0;
        }
    </script>
</body>
</html>
            '''
            self.wfile.write(html.encode())
            
        elif self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Start real-time log monitoring
            self.stream_logs()
        else:
            super().do_GET()
    
    def stream_logs(self):
        """Stream logs in real-time using Server-Sent Events"""
        try:
            # Get all running containers
            result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], 
                                 capture_output=True, text=True)
            containers = result.stdout.strip().split('\n')
            
            # Start monitoring each container
            for container in containers:
                if container:
                    threading.Thread(target=self.monitor_container, args=(container,), daemon=True).start()
            
            # Keep connection alive and send heartbeat
            while True:
                self.wfile.write(b'data: {"timestamp":"' + datetime.now().isoformat().encode() + b'","container":"SYSTEM","message":"Heartbeat","level":"info"}\n\n')
                self.wfile.flush()
                time.sleep(30)  # Heartbeat every 30 seconds
                
        except Exception as e:
            error_msg = {
                'timestamp': datetime.now().isoformat(),
                'container': 'SYSTEM',
                'message': f'Streaming error: {str(e)}',
                'level': 'error'
            }
            self.wfile.write(f'data: {json.dumps(error_msg)}\n\n'.encode())
            self.wfile.flush()
    
    def monitor_container(self, container_name):
        """Monitor a single container's logs in real-time"""
        try:
            # Use docker logs with follow flag for real-time streaming
            process = subprocess.Popen(
                ['docker', 'logs', '-f', '--timestamps', container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                if line.strip():
                    # Parse timestamp and message
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        timestamp = parts[0]
                        message = parts[1].strip()
                        
                        # Determine log level
                        level = 'info'
                        if 'ERROR' in message.upper() or 'error' in message.lower():
                            level = 'error'
                        elif 'WARN' in message.upper() or 'warning' in message.lower():
                            level = 'warning'
                        
                        log_entry = {
                            'timestamp': timestamp,
                            'container': container_name,
                            'message': message,
                            'level': level
                        }
                        
                        # Send via Server-Sent Events
                        try:
                            self.wfile.write(f'data: {json.dumps(log_entry)}\n\n'.encode())
                            self.wfile.flush()
                        except:
                            break  # Connection closed
                
        except Exception as e:
            error_msg = {
                'timestamp': datetime.now().isoformat(),
                'container': container_name,
                'message': f'Monitoring error: {str(e)}',
                'level': 'error'
            }
            try:
                self.wfile.write(f'data: {json.dumps(error_msg)}\n\n'.encode())
                self.wfile.flush()
            except:
                pass

if __name__ == '__main__':
    PORT = 8080
    with socketserver.TCPServer(("", PORT), RealTimeLogHandler) as httpd:
        print(f"🔴 Real-Time Log Viewer running at http://localhost:{PORT}")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()
EOF

# Make it executable
chmod +x realtime_log_server.py

# Create systemd service
cat > /etc/systemd/system/realtime-log-viewer.service << EOF
[Unit]
Description=Real-Time Log Viewer
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/realtime-logs
ExecStart=/usr/bin/python3 /opt/realtime-logs/realtime_log_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable realtime-log-viewer
systemctl start realtime-log-viewer

# Check if service is running
if systemctl is-active --quiet realtime-log-viewer; then
    echo "✅ Real-Time Log Viewer is running"
else
    echo "❌ Real-Time Log Viewer failed to start"
    systemctl status realtime-log-viewer
    exit 1
fi

echo ""
echo "🎉 Real-Time Log Viewer deployed!"
echo ""
echo "📊 Access your logs at:"
echo "   - Web Interface: http://YOUR_DROPLET_IP:8080"
echo ""
echo "🔴 Features:"
echo "   - REAL-TIME streaming (logs appear as they happen)"
echo "   - Live statistics (total logs, errors, warnings)"
echo "   - Color-coded log levels"
echo "   - All Docker containers"
echo "   - Auto-scroll to bottom"
echo ""
echo "📝 Management:"
echo "   - Start: systemctl start realtime-log-viewer"
echo "   - Stop: systemctl stop realtime-log-viewer"
echo "   - Status: systemctl status realtime-log-viewer"
echo "   - Logs: journalctl -u realtime-log-viewer -f"
echo ""
echo "💡 Usage:"
echo "   1. Open http://YOUR_DROPLET_IP:8080"
echo "   2. Click 'Start Streaming'"
echo "   3. Watch logs appear in real-time!" 