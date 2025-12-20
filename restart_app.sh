#!/bin/bash
# Bash script to restart Aphorium API server and frontend
# Usage: ./restart_app.sh

echo "Restarting Aphorium..."

# Stop the servers
./stop_app.sh

# Wait a moment
sleep 2

# Start the servers
./start_app.sh
