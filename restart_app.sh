#!/bin/bash
# Bash script to restart Aphorium API server
# Usage: ./restart_app.sh

echo "Restarting Aphorium API server..."

# Stop the server
./stop_app.sh

# Wait a moment
sleep 2

# Start the server
./start_app.sh

