#!/usr/bin/env bash
# Ground truth on the SSH host: server, pty host and the shells/markers started by the POC.
# Usage (from the PC):  ssh -p 2222 root@nas bash -s < poc/nas-state.sh
echo "server:  $(pgrep -f 'out/server-main.js' | tr '\n' ' ')"
PTY=$(pgrep -f 'type=ptyHost' | head -1)
echo "ptyHost: ${PTY:-none}"
echo "markers (poc-*):"
ps -eo pid,ppid,etimes,args | awk '$4 ~ /^poc-/ {print "  " $0}'
if [ -n "$PTY" ]; then
	echo "pty children:"
	ps -o pid,etimes,args --ppid "$PTY" | sed 's/^/  /'
fi
