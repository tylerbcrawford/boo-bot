#!/bin/sh
set -e

echo "Installing system dependencies (ffmpeg for trailer compression)..."
apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null 2>&1

echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "Starting Discord bot..."
exec python -u bot.py
