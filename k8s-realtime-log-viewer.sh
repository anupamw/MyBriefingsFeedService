#!/bin/bash

# K8s Real-Time Log Viewer - Shows logs from Kubernetes pods as they happen
# Uses Server-Sent Events for live streaming

set -e

echo "🚀 Starting K8s Real-Time Log Viewer..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root or with sudo"
    exit 1
fi

# Install required packages
echo "📦 Installing required packages..."
apt update && apt install -y python3 python3-pip curl

# Create real-time log viewer for k8s
mkdir -p /opt/k8s-realtime-logs
cd /opt/k8s-realtime-logs

# Create Python web server with real-time streaming for k8s
cat > k8s_realtime_log_server.py << 'EOF'
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

class K8sRealTimeLogHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = '''
<!DOCTYPE html>
<html>
<head>
    <title>K8s Real-Time Log Viewer</title>
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
        .pod-name { color: #00ff00; font-weight: bold; }
        .message { color: #fff; }
        .status { color: #00ff00; }
        .connection-status { color: #ff6b6b; }
        .stats { background: #333; padding: 10px; border-radius: 3px; margin-bottom: 10px; }
        .namespace { color: #ffa500; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔴 K8s Real-Time Log Viewer</h1>
            <p>Live streaming logs from your application services only</p>
        </div>
        
        <div class="stats" id="stats">
            <strong>📊 Stats:</strong> 
            <span id="total-logs">0</span> logs | 
            <span id="errors">0</span> errors | 
            <span id="warnings">0</span> warnings |
            <span id="pods">0</span> pods |
            <span id="namespaces">0</span> namespaces
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
                <span class="pod-name">SYSTEM:</span>
                <span class="message">K8s real-time log viewer started. Click "Start Streaming" to begin.</span>
            </div>
        </div>
    </div>

    <script>
        let eventSource = null;
        let isStreaming = false;
        let totalLogs = 0;
        let errorCount = 0;
        let warningCount = 0;
        let pods = new Set();
        let namespaces = new Set();
        
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
            
            const pod = document.createElement('span');
            pod.className = 'pod-name';
            pod.textContent = log.pod + ':';
            
            const namespace = document.createElement('span');
            namespace.className = 'namespace';
            namespace.textContent = ' (' + log.namespace + ')';
            
            const message = document.createElement('span');
            message.className = 'message';
            message.textContent = log.message;
            
            logLine.appendChild(timestamp);
            logLine.appendChild(pod);
            logLine.appendChild(namespace);
            logLine.appendChild(message);
            logsDiv.appendChild(logLine);
            
            // Auto-scroll to bottom
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
        
        function updateStats(log) {
            totalLogs++;
            pods.add(log.pod);
            namespaces.add(log.namespace);
            
            if (log.level === 'error') errorCount++;
            if (log.level === 'warning') warningCount++;
            
            document.getElementById('total-logs').textContent = totalLogs;
            document.getElementById('errors').textContent = errorCount;
            document.getElementById('warnings').textContent = warningCount;
            document.getElementById('pods').textContent = pods.size;
            document.getElementById('namespaces').textContent = namespaces.size;
        }
        
        function clearLogs() {
            document.getElementById('logs').innerHTML = '';
            totalLogs = 0;
            errorCount = 0;
            warningCount = 0;
            pods.clear();
            namespaces.clear();
            updateStats({pod: '', namespace: '', level: 'info'});
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
            import threading
            import time
            self.active_pods = set()
            self.pod_threads = {}
            self.lock = threading.Lock()

            def discover_pods():
                app_namespaces = ['default', 'my-briefings']
                app_pod_patterns = ['my-briefings', 'app', 'celery', 'worker', 'ingestion']
                while True:
                    new_pods = set()
                    for namespace in app_namespaces:
                        try:
                            result = subprocess.run([
                                'kubectl', 'get', 'pods', '-n', namespace, '--no-headers', '-o', 'custom-columns=NAME:.metadata.name'
                            ], capture_output=True, text=True)
                            if result.stdout.strip():
                                for pod_name in result.stdout.strip().split('\n'):
                                    if pod_name.strip():
                                        pod_lower = pod_name.lower()
                                        if any(pattern.lower() in pod_lower for pattern in app_pod_patterns):
                                            new_pods.add((namespace, pod_name.strip()))
                        except Exception as e:
                            print(f"Error getting pods from namespace {namespace}: {e}")
                    with self.lock:
                        for pod in new_pods:
                            if pod not in self.active_pods:
                                t = threading.Thread(target=self.monitor_pod, args=(pod[0], pod[1]), daemon=True)
                                t.start()
                                self.pod_threads[pod] = t
                                self.active_pods.add(pod)
                    time.sleep(10)  # Check every 10 seconds

            threading.Thread(target=discover_pods, daemon=True).start()

            # Keep connection alive and send heartbeat
            while True:
                self.wfile.write(b'data: {"timestamp":"' + datetime.now().isoformat().encode() + b'","pod":"SYSTEM","namespace":"system","message":"Heartbeat","level":"info"}\n\n')
                self.wfile.flush()
                time.sleep(30)  # Heartbeat every 30 seconds
                
        except Exception as e:
            error_msg = {
                'timestamp': datetime.now().isoformat(),
                'pod': 'SYSTEM',
                'namespace': 'system',
                'message': f'Streaming error: {str(e)}',
                'level': 'error'
            }
            self.wfile.write(f'data: {json.dumps(error_msg)}\n\n'.encode())
            self.wfile.flush()
    
    def monitor_pod(self, namespace, pod_name):
        """Monitor a single pod's logs in real-time"""
        try:
            # Use kubectl logs with follow flag for real-time streaming
            process = subprocess.Popen(
                ['kubectl', 'logs', '-f', '--timestamps', '-n', namespace, pod_name],
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
                            'pod': pod_name,
                            'namespace': namespace,
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
                'pod': pod_name,
                'namespace': namespace,
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
    with socketserver.TCPServer(("", PORT), K8sRealTimeLogHandler) as httpd:
        print(f"🔴 K8s Real-Time Log Viewer running at http://localhost:{PORT}")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()
EOF

# Make it executable
chmod +x k8s_realtime_log_server.py

# Create systemd service
cat > /etc/systemd/system/k8s-realtime-log-viewer.service << EOF
[Unit]
Description=K8s Real-Time Log Viewer
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/k8s-realtime-logs
ExecStart=/usr/bin/python3 /opt/k8s-realtime-logs/k8s_realtime_log_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable k8s-realtime-log-viewer
systemctl start k8s-realtime-log-viewer

# Check if service is running
if systemctl is-active --quiet k8s-realtime-log-viewer; then
    echo "✅ K8s Real-Time Log Viewer is running"
else
    echo "❌ K8s Real-Time Log Viewer failed to start"
    systemctl status k8s-realtime-log-viewer
    exit 1
fi

echo ""
echo "🎉 K8s Real-Time Log Viewer deployed!"
echo ""
echo "📊 Access your logs at:"
echo "   - Web Interface: http://YOUR_DROPLET_IP:8080"
echo ""
echo "🔴 Features:"
echo "   - REAL-TIME streaming (logs appear as they happen)"
echo "   - Live statistics (total logs, errors, warnings, pods, namespaces)"
echo "   - Color-coded log levels"
echo "   - Your application services only (no system pods)"
echo "   - Namespace information"
echo "   - Auto-scroll to bottom"
echo ""
echo "📝 Management:"
echo "   - Start: systemctl start k8s-realtime-log-viewer"
echo "   - Stop: systemctl stop k8s-realtime-log-viewer"
echo "   - Status: systemctl status k8s-realtime-log-viewer"
echo "   - Logs: journalctl -u k8s-realtime-log-viewer -f"
echo ""
echo "💡 Usage:"
echo "   1. Open http://YOUR_DROPLET_IP:8080"
echo "   2. Click 'Start Streaming'"
echo "   3. Watch logs from all your k8s pods in real-time!" 