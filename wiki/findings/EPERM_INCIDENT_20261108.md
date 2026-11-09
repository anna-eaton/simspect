# EPERM incident audit — ~/Documents lost all access for ~30–60 min on 2026-11-08

Written 2026-11-09 by a fresh Claude Code session (Opus 4.8), read-only. No files changed, nothing deleted. This file is the durable record of the audit.

## Verdict up front

**The lockout was an iCloud "Desktop & Documents Folders" (CloudDocs / File Provider) on-demand-materialization fault — not anything the Mythos session did.** The Mythos session ran only read-only inspection commands plus one markdown-doc append, finished ~1 hour before the lockout began, and never touched permissions, flags, ACLs, TCC, launchd, or anything system-level. There is no evidence of tampering by any Claude session.

## Correction: it was NOT a flat wall over all of Documents (Anna's observation, confirmed)

`~/Documents` itself kept working the whole time — `stat`/`ls -d` on the folder and its immediate inodes always succeeded. What faulted was **reading file data and enumerating specific deep subtrees** (`.claude`, `quail/tools`, `stanford/trippel/simspect`). The preserved capture shows exactly this split: `ls -lOde@` (which only `stat`s, because of the `-d`) returned normally for `~/Documents`, `~/Documents/.claude`, and `~/Documents/quail/tools`, while `ls -la ~/Documents/.claude` (which *enumerates contents*) returned `Operation not permitted`, and the shell glob `~/Documents/.claude/*` collapsed to "No such file or directory" because the directory couldn't be read.

**Mechanism (now precise).** `~/Documents` is the iCloud File Provider domain root (`com.apple.fileprovider.detached#B`, `com.apple.icloud.desktop`). Files under it that aren't pinned get evicted to **dataless cloud placeholders**: the name/inode is local (so `stat` works) but the data lives in iCloud and must be *materialized on demand* when read. At audit time, `~/Documents/quail` is explicitly **pinned** (`com.apple.fileprovider.pinned#PX`, 0 dataless items) while `~/trippel/simspect` is **not pinned and currently has dataless items**. When `bird` (CloudDocs) stalled at 23:02, every on-demand materialization request EPERM'd — so `stat` of a placeholder still worked, but reading/enumerating the dataless subtree faulted. That is precisely "Documents worked, the stuff below faulted," and it defeats `sudo` because materialization is a provider operation, not a uid-permission check. Finder kept working because it reads placeholders and triggers download through the provider's own UI path.

## Timeline (all times PST, 2026-11-08)

- **21:47** — Mythos 5.1 session `eb458662` starts in simspect (model confirmed from the session's own cost-state record: `claude-mythos-5-1`).
- **21:53–22:03** — The session runs 33 tool calls: all read-only (`head`/`sed`/`grep`/`cat`/`diff`/`ls`/`find`/`df`) except one `python` heredoc that appended a write-up section to `wiki/state/ALLOY_MODEL_CHANGES.md`. No `.als`, no code, no config, no permissions touched.
- **22:07** — Session goes idle (its last away-summary). From here on Mythos does nothing.
- **23:02:49–23:02:51** — `~/Documents`, `stanford`, `trippel`, `simspect` all get their mtime/ctime bumped within the same ~2-second window. This is the File Provider walking/detaching the managed tree.
- **23:02** — `bird` (the iCloud CloudDocs daemon) throws its error burst: 20+ errors that minute (XPC connection cancellations, failed thumbnail generation, repeated upload cycles). This is the fault moment.
- **23:12** — A separate debug session (Opus) is started from `~/Documents` and immediately hits `EPERM: operation not permitted` on every read under `~/Documents` — settings files, the `webgate.py` Bash hook, everything. Terminal itself (with Full Disk Access, and even with `sudo`) also could not `ls` the tree.
- **23:02 → ~23:36** — `bird` keeps throwing trailing errors (23:07, 23:13, 23:15, 23:26, 23:34, 23:36).
- **~23:37** — Access returns on its own. The debug session can read `~/Documents/.claude` and `webgate.py` again; `ls` works. No intervention was needed.

## Why this is CloudDocs/File Provider and not a permissions change

- **`sudo` also got EPERM.** Normal file modes, a `uchg` immutable flag, and deny-ACLs are all either bypassable by root or visible in metadata. The metadata showed none of them — no `uchg`, no deny ACLs, normal owner/mode. An EPERM that defeats root but leaves metadata pristine is the signature of a VFS-level provider refusal, not a stored permission.
- **Only the iCloud-managed tree was affected.** `~/Documents` carries `com.apple.fileprovider.detached#B` and `com.apple.icloud.desktop` xattrs — it is a File Provider managed domain. The lockout covered exactly that subtree and nothing else on the Mac.
- **Finder still showed the files.** Finder talks to `fileproviderd` directly (placeholders), so it stays readable while direct `open()` calls through the VFS get EPERM. That split is characteristic of a File Provider stall.
- **It self-healed.** A permission change persists until something changes it back. This lifted by itself as `bird` settled — consistent with the daemon finishing its domain operation.
- **The macOS unified log shows no kernel-sandbox deny on "Documents" in the window, and no permission-changing command anywhere.** The only "Operation not permitted" lines in 23:00–23:40 come from unrelated daemons (`findmylocateagent`, WebKit, `peopled`, AppleIDSettings) doing their own Find My / Apple ID work — none reference Documents, Claude, or a sandbox.

## What the Mythos session did NOT do (checked explicitly)

Zero occurrences, across all 33 tool calls, of: `chflags`, `chmod`, `chown`, `xattr`, `tccutil`, `sqlite3` (TCC.db), `launchctl`, `crontab`, `sudo`, `defaults write`, `csrutil`, `spctl`, `sandbox-exec`, `/Library` writes, LaunchAgents/LaunchDaemons edits, `authorized_keys`, `ssh-keygen`. The earlier debug session's cross-transcript scan (all sessions, Oct 13 → Nov 9) likewise found none of these as executed commands.

## Likely trigger

A near-full disk (93% used, 66 GiB free at audit time) plus heavy file churn in the iCloud-managed `~/Documents` — many concurrent Claude sessions writing thousands of generated files, plus repeated `make sync` git activity — is exactly what pushes CloudDocs/`bird` into a stall where it detaches and re-materializes the domain. During that operation the tree EPERMs for everyone. This is a macOS/iCloud robustness problem, not a security event.

## Current state

Access fully restored. No abnormal flags or ACLs remain on the tree. No persistent breakage found locally.

## Still open / not done here

- **cafe2 was not actually connected to.** Only the local transcripts were analyzed (they show only expected hosts — cafe2, the Mac mini, the `sc` jump host — no tunnels, no key writes, no `sudo`, remote deletes limited to today's smoke-test dirs inside the `gem5_dev` container). A live read-only check of cafe2 is a separate step, not yet run.

## Evidence locations (preserved, read-only)

- Mythos session transcript: `~/.claude/projects/-Users-annaeaton-Documents-stanford-trippel-simspect/eb458662-6aaa-4f60-8e2b-9fa94c8dc2a5.jsonl`
- Debug session transcript: `~/.claude/projects/-Users-annaeaton-Documents/48ba82cc-ae8d-4cd7-9bf3-7db784844376.jsonl`
- The debug session's own preserved snapshot folder: `~/claude-incident-2026-11-08/` (and `~/claude-incident-2026-11-08-volatile/`)
- macOS log for the window, reproducible with: `log show --start "2026-11-08 23:00:00" --end "2026-11-08 23:40:00" --predicate 'process == "bird"' --style compact`
