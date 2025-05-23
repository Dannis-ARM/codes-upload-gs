#!/bin/bash

# Define the log file path
LOG_FILE="/var/log/myapp.log"

# Function to write log messages with severity level
log_message() {
    local severity="$1"
    local message="$2"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    local log_entry="[$severity] [$timestamp] $message"
    
    # Write the log message to both the log file and stdout using tee
    echo "$log_entry" | tee -a "$LOG_FILE"
}

# Example usage
log_message "INFO" "This is an informational message."
log_message "WARNING" "This is a warning message."
log_message "ERROR" "This is an error message."
log_message "DEBUG" "This is a debug message."