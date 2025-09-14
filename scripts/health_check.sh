#!/bin/bash

# Health check script for Instagram Content Generator
# This script is used by Docker healthcheck and external monitoring

set -e

# Configuration
HEALTH_CHECK_URL="http://localhost:${HEALTH_CHECK_PORT:-8080}/health"
TIMEOUT=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if the service is responding
check_health() {
    local response
    local http_code
    
    # Try to connect to health endpoint
    if command -v curl >/dev/null 2>&1; then
        response=$(curl -s -w "%{http_code}" --max-time $TIMEOUT "$HEALTH_CHECK_URL" 2>/dev/null || echo "000")
        http_code="${response: -3}"
        response="${response%???}"
    else
        log "curl not found, falling back to basic check"
        return 1
    fi
    
    # Check HTTP status code
    case $http_code in
        200)
            log "${GREEN}✓${NC} Service is healthy (HTTP $http_code)"
            
            # Parse response for additional details
            if command -v python3 >/dev/null 2>&1; then
                status=$(echo "$response" | python3 -c "
import json
import sys
try:
    data = json.load(sys.stdin)
    print(f\"Status: {data.get('status', 'unknown')}\")
    if 'uptime_seconds' in data:
        uptime = int(data['uptime_seconds'])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        print(f\"Uptime: {hours}h {minutes}m\")
    if 'issues' in data and data['issues']:
        print(f\"Issues: {', '.join(data['issues'])}\")
except:
    pass
                " 2>/dev/null)
                
                if [ -n "$status" ]; then
                    log "$status"
                fi
            fi
            return 0
            ;;
        503)
            log "${YELLOW}⚠${NC} Service is unhealthy (HTTP $http_code)"
            return 1
            ;;
        000)
            log "${RED}✗${NC} Service is not responding (connection failed)"
            return 1
            ;;
        *)
            log "${RED}✗${NC} Service returned unexpected status (HTTP $http_code)"
            return 1
            ;;
    esac
}

# Function to check system resources
check_system() {
    log "System resource check:"
    
    # Check disk space
    if command -v df >/dev/null 2>&1; then
        disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
        if [ "$disk_usage" -gt 90 ]; then
            log "${RED}✗${NC} Disk usage critical: ${disk_usage}%"
            return 1
        elif [ "$disk_usage" -gt 80 ]; then
            log "${YELLOW}⚠${NC} Disk usage high: ${disk_usage}%"
        else
            log "${GREEN}✓${NC} Disk usage: ${disk_usage}%"
        fi
    fi
    
    # Check memory if available
    if [ -f /proc/meminfo ]; then
        mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        mem_usage=$((100 - (mem_available * 100 / mem_total)))
        
        if [ "$mem_usage" -gt 90 ]; then
            log "${RED}✗${NC} Memory usage critical: ${mem_usage}%"
            return 1
        elif [ "$mem_usage" -gt 80 ]; then
            log "${YELLOW}⚠${NC} Memory usage high: ${mem_usage}%"
        else
            log "${GREEN}✓${NC} Memory usage: ${mem_usage}%"
        fi
    fi
    
    # Check CPU temperature (Raspberry Pi specific)
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        temp=$(cat /sys/class/thermal/thermal_zone0/temp)
        temp_celsius=$((temp / 1000))
        
        if [ "$temp_celsius" -gt 80 ]; then
            log "${RED}✗${NC} CPU temperature critical: ${temp_celsius}°C"
            return 1
        elif [ "$temp_celsius" -gt 70 ]; then
            log "${YELLOW}⚠${NC} CPU temperature high: ${temp_celsius}°C"
        else
            log "${GREEN}✓${NC} CPU temperature: ${temp_celsius}°C"
        fi
    fi
    
    return 0
}

# Function to check log files for errors
check_logs() {
    local log_file="/var/log/instagram-content-generator.log"
    local error_log="/var/log/errors.log"
    
    # Check if log files exist and are being written to
    if [ -f "$log_file" ]; then
        local last_log_time
        last_log_time=$(stat -c %Y "$log_file" 2>/dev/null || echo 0)
        local current_time
        current_time=$(date +%s)
        local time_diff=$((current_time - last_log_time))
        
        if [ "$time_diff" -gt 3600 ]; then  # No logs for 1 hour
            log "${YELLOW}⚠${NC} No recent log activity (${time_diff}s ago)"
        else
            log "${GREEN}✓${NC} Log file active (${time_diff}s ago)"
        fi
    else
        log "${YELLOW}⚠${NC} Main log file not found"
    fi
    
    # Check for recent errors
    if [ -f "$error_log" ]; then
        local recent_errors
        recent_errors=$(tail -50 "$error_log" 2>/dev/null | grep "$(date '+%Y-%m-%d')" | wc -l)
        
        if [ "$recent_errors" -gt 10 ]; then
            log "${RED}✗${NC} High error count today: $recent_errors"
            return 1
        elif [ "$recent_errors" -gt 0 ]; then
            log "${YELLOW}⚠${NC} Errors today: $recent_errors"
        else
            log "${GREEN}✓${NC} No errors today"
        fi
    fi
    
    return 0
}

# Function to check required directories
check_directories() {
    local required_dirs=("/shared" "/processed" "/var/log")
    local missing_dirs=0
    
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            log "${RED}✗${NC} Required directory missing: $dir"
            missing_dirs=$((missing_dirs + 1))
        elif [ ! -w "$dir" ]; then
            log "${RED}✗${NC} Directory not writable: $dir"
            missing_dirs=$((missing_dirs + 1))
        else
            log "${GREEN}✓${NC} Directory accessible: $dir"
        fi
    done
    
    return $missing_dirs
}

# Main health check function
main() {
    local exit_code=0
    local checks_failed=0
    
    log "Starting health check for Instagram Content Generator"
    
    # Check service health endpoint
    if ! check_health; then
        exit_code=1
        checks_failed=$((checks_failed + 1))
    fi
    
    # Check system resources
    if ! check_system; then
        checks_failed=$((checks_failed + 1))
        # Don't fail health check for system issues, just warn
    fi
    
    # Check log files
    if ! check_logs; then
        checks_failed=$((checks_failed + 1))
        # Don't fail health check for log issues, just warn
    fi
    
    # Check required directories
    if ! check_directories; then
        exit_code=1
        checks_failed=$((checks_failed + 1))
    fi
    
    # Summary
    if [ $exit_code -eq 0 ]; then
        log "${GREEN}✓${NC} Health check passed"
        if [ $checks_failed -gt 0 ]; then
            log "${YELLOW}⚠${NC} $checks_failed non-critical issues detected"
        fi
    else
        log "${RED}✗${NC} Health check failed ($checks_failed critical issues)"
    fi
    
    return $exit_code
}

# Handle command line arguments
case "${1:-check}" in
    check|health)
        main
        ;;
    system)
        check_system
        ;;
    logs)
        check_logs
        ;;
    dirs|directories)
        check_directories
        ;;
    service)
        check_health
        ;;
    --help|-h)
        echo "Usage: $0 [check|system|logs|dirs|service]"
        echo ""
        echo "Commands:"
        echo "  check     - Full health check (default)"
        echo "  system    - Check system resources only"
        echo "  logs      - Check log files only"
        echo "  dirs      - Check required directories only"
        echo "  service   - Check service endpoint only"
        echo ""
        exit 0
        ;;
    *)
        echo "Unknown command: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac