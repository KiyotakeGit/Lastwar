#!/bin/bash
echo "================================"
echo "  Last War Automation - Build"
echo "================================"
echo

echo "[1/3] Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo
echo "[2/3] Building executable..."
pyinstaller lastwar.spec --noconfirm

echo
echo "[3/3] Done!"
echo
echo "Output: dist/LastWarAutomation"
