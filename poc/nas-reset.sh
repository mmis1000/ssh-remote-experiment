#!/usr/bin/env bash
# Stops every dev server, pty host and POC marker on the SSH host, for a clean run.
# Usage (from the PC):  ssh -p 2222 root@nas bash -s < poc/nas-reset.sh
pkill -f '[c]odium-server --start-server'
pkill -f '[o]ut/server-main.js'
pkill -f '[o]ut/bootstrap-fork'
pkill -f '^poc-'
sleep 1
rm -f ~/.vscodium-server/.deadc0de*.pid ~/.vscodium-server/.deadc0de*.token
echo "left: $(pgrep -fc '[o]ut/(server-main|bootstrap-fork)') server/host processes, $(pgrep -fc '^poc-') markers"
