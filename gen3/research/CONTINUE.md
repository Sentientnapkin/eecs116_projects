# Continuation instructions (Sonnet takeover, 2026-11-26)
A previous agent (stopped to save usage) already started your task in your work dir. First, inspect what exists there
(NOTES.md, scripts, logs, results.tsv, running processes via `ps -eo pid,args | grep <your dir>`) — do NOT redo finished work and
do NOT start duplicate copies of pipelines that are already running. Then: finish any setup, launch the remaining work as ONE
detached resumable pipeline (nohup setsid, queue + done markers + results.tsv), wait with a single long until-loop (≥15 min
interval) on its done marker, analyse the summaries, and write the deliverable. Keep tool output small (tail/head/grep, never cat
large files). Be concise in reasoning.
