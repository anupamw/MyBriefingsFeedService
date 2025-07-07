#!/bin/bash

# Enhanced Log Aggregator for Kubernetes Pods with Timeseries View
# This script collects logs from all pods and creates a timeseries view

NAMESPACE="my-briefings"
LOG_DIR="/var/log/my-briefings"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REALTIME_LOG="$LOG_DIR/realtime.log"

# Create log directory
mkdir -p $LOG_DIR

# Function to get logs with timestamps
get_pod_logs() {
    local pod=$1
    local since=${2:-"1h"}  # Default to last hour
    
    echo "=== POD: $pod (since $since) ==="
    kubectl logs -n $NAMESPACE $pod --all-containers=true --timestamps=true --since=$since 2>/dev/null | \
    while IFS= read -r line; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $pod: $line"
    done
}

# Function to create timeseries log
create_timeseries_log() {
    local output_file=$1
    local since=${2:-"1h"}
    
    echo "Creating timeseries log: $output_file (since $since)"
    echo "=== TIMESERIES LOG STARTED AT $(date) ===" > "$output_file"
    
    # Get all pods
    PODS=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')
    
    for pod in $PODS; do
        echo "Collecting logs from: $pod"
        get_pod_logs "$pod" "$since" >> "$output_file"
    done
    
    echo "=== TIMESERIES LOG COMPLETED AT $(date) ===" >> "$output_file"
}

# Function to view real-time logs
view_realtime_logs() {
    echo "Starting real-time log monitoring..."
    echo "Press Ctrl+C to stop"
    echo "Logs will be saved to: $REALTIME_LOG"
    echo ""
    
    # Clear the realtime log file
    > "$REALTIME_LOG"
    
    # Start monitoring all pods in real-time
    kubectl logs -n $NAMESPACE -f --all-containers=true --timestamps=true --selector=app 2>/dev/null | \
    while IFS= read -r line; do
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        echo "[$timestamp] $line" | tee -a "$REALTIME_LOG"
    done
}

# Function to view logs by time range
view_logs_by_time() {
    local since=$1
    local output_file="$LOG_DIR/timeseries_${TIMESTAMP}.log"
    
    create_timeseries_log "$output_file" "$since"
    
    echo ""
    echo "Timeseries log created: $output_file"
    echo "To view it: cat $output_file"
    echo "To tail it: tail -f $output_file"
}

# Function to search logs
search_logs() {
    local search_term=$1
    local since=${2:-"1h"}
    
    echo "Searching logs for: '$search_term' (since $since)"
    echo "Results:"
    echo ""
    
    kubectl logs -n $NAMESPACE --all-containers=true --timestamps=true --since=$since 2>/dev/null | \
    grep -i "$search_term" | \
    while IFS= read -r line; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
    done
}

# Function to show log statistics
show_log_stats() {
    echo "=== LOG STATISTICS ==="
    echo "Namespace: $NAMESPACE"
    echo "Timestamp: $(date)"
    echo ""
    
    # Pod status
    echo "Pod Status:"
    kubectl get pods -n $NAMESPACE -o wide
    echo ""
    
    # Log file sizes
    echo "Log File Sizes:"
    if [ -d "$LOG_DIR" ]; then
        ls -lh "$LOG_DIR"/*.log 2>/dev/null || echo "No log files found"
    else
        echo "Log directory not found"
    fi
    echo ""
    
    # Recent errors
    echo "Recent Errors (last 10 minutes):"
    kubectl logs -n $NAMESPACE --all-containers=true --timestamps=true --since=10m 2>/dev/null | \
    grep -i "error\|exception\|failed" | tail -10
}

# Main script logic
case "${1:-help}" in
    "realtime"|"rt")
        view_realtime_logs
        ;;
    "timeseries"|"ts")
        view_logs_by_time "${2:-1h}"
        ;;
    "search"|"s")
        if [ -z "$2" ]; then
            echo "Usage: $0 search <search_term> [time_range]"
            echo "Example: $0 search 'error' '30m'"
            exit 1
        fi
        search_logs "$2" "${3:-1h}"
        ;;
    "stats")
        show_log_stats
        ;;
    "cleanup")
        echo "Cleaning up old log files (keeping last 7 days)..."
        find $LOG_DIR -name "*.log" -mtime +7 -delete
        echo "Cleanup completed"
        ;;
    "help"|*)
        echo "Enhanced Log Aggregator for Kubernetes"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  realtime, rt     - View real-time logs from all pods"
        echo "  timeseries, ts   - Create timeseries log (default: last 1h)"
        echo "  search, s        - Search logs for specific terms"
        echo "  stats            - Show log statistics and pod status"
        echo "  cleanup          - Clean up old log files"
        echo "  help             - Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 realtime                    # View real-time logs"
        echo "  $0 timeseries 30m              # Create timeseries for last 30 minutes"
        echo "  $0 search 'error' 1h          # Search for 'error' in last hour"
        echo "  $0 stats                       # Show statistics"
        echo ""
        echo "Time ranges: 30s, 1m, 5m, 30m, 1h, 2h, 1d"
        ;;
esac 