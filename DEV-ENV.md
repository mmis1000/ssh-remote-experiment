# Development environment for the persistent-terminal POC

Date: 2026-10-15. Goes with [PROPOSAL-v2.md](PROPOSAL-v2.md).
Base: VSCodium `upstream/stable.json` pins VS Code **1.140.0**, commit `07f806f9`. That commit needs Node **24.18.0** for the build and **24.21.0** for the server runtime, and its client uses Electron 43.7.3.

## Recommendation

| Machine | Role | Needed? |
| --- | --- | --- |
| Cloud container (where Claude works) | Write and test the server, pty host and workbench changes. Run automated two-window tests. | Yes. This was tested and works (see below). |
| GitHub Actions on your VSCodium fork | Build the Windows client and the Linux server tarball, then publish them as a release on the fork. | Yes. It replaces a local Windows build toolchain. |
| Your Windows PC | Run the built VSCodium zip with Open Remote SSH, and try the real close, reload and sleep behavior. | Yes, as the test client. You don't need a build toolchain on it. |
| Linux SSH host | The remote that the acceptance scenarios run against. | Yes. Any x64 Linux host with sshd works. |
| Your fast storage | A faster way to get a server build from the container to the SSH host than a full CI run. | Optional (see the last section). |

## 1. Cloud container: tested

This container has 4 cores, 15 GB of RAM and about 31 GB of free disk.

| Step | Result |
| --- | --- |
| `git fetch` of the pinned VS Code commit | 5 s, 392 MB |
| `npm ci` | About 8 minutes; the checkout grew to 7.2 GB |
| `npm run compile-client` | 2.3 minutes, 0 errors |
| `scripts/code-server.sh` (the server from source, with the web workbench) | Starts in a few seconds |
| Playwright with headless Chromium: open the workbench, then open a terminal | Worked: a pty host process started and bash ran on `/dev/pts/0` |
| `gulp vscode-reh-linux-x64-min` (the packaged server tarball) | **Failed.** The build looks up GitHub releases for the built-in extensions through `api.github.com`, and this container's proxy refuses lookups for repositories that aren't attached to it (403). |

Workarounds that the container's network makes necessary. They are local only and committed nowhere:
- electronjs.org is blocked, so the Electron headers can't be downloaded. Native modules were built against Node instead, with `npm_config_runtime=node`, `npm_config_target=24.21.0` and `npm_config_disturl=https://nodejs.org/dist`, plus `ELECTRON_SKIP_BINARY_DOWNLOAD=1`. `build/npm/preinstall.ts` was also patched temporarily to skip the Electron header download. **So the Electron desktop client can't be built here.**
- The `@vscode/ripgrep` postinstall fails for the same api.github.com reason. Fix: download `ripgrep-v15.0.1-x86_64-unknown-linux-musl.tar.gz` directly from the GitHub release into `$TMPDIR/vscode-ripgrep-cache-1.17.1/` first.
- open-vsx.org, deb.debian.org and update.code.visualstudio.com are blocked. GitHub (git, plus direct release downloads), npm, nodejs.org, PyPI and archive.ubuntu.com all work.

What this means: almost all of the POC code (changes 1 to 6) lives in the server, the pty host or the workbench. The web workbench runs that same workbench code, so two browser tabs can stand in for two windows. Reload, tab close and the lifetime, attach, list and sizing logic can all be tested automatically here. **What the container can't test** is the desktop-specific behavior: Electron window close and quit, laptop sleep, and Open Remote SSH's real launch flags (`--enable-remote-auto-shutdown`). Those need the Windows client.

The container is ephemeral, so all code has to be pushed to GitHub forks.

## 2. Repositories to create and attach to this project

- `mmis1000/vscode`: a fork of microsoft/vscode with a branch from the pinned commit `07f806f9`. This is where the code is written and reviewed.
- `mmis1000/vscodium`: a fork of VSCodium. The change lands as a patch under `patches/`, and its workflows build and publish the releases. Make it **public**: Open Remote SSH downloads the server on the remote with a plain `wget`/`curl` and no authentication (`src/scripts/server-setup.sh:166`), so assets from a private repository won't download.
- `mmis1000/open-remote-ssh`: a fork of jeanp413/open-remote-ssh. It only needs a different default `serverDownloadUrlTemplate`. For the POC you can instead set `remote.SSH.serverDownloadUrlTemplate` in settings.

## 3. Builds with GitHub Actions

VSCodium's own `publish-stable-windows.yml` and `publish-stable-linux.yml` already build the Windows client (on `windows-2022`) and the Linux server tarball (`reh_linux` on `ubuntu-22.04`). They upload to the fork's own releases (`ASSETS_REPOSITORY: github.repository`). Point `serverDownloadUrlTemplate` at
`https://github.com/mmis1000/vscodium/releases/download/${version}.${release}/vscodium-reh-${os}-${arch}-${version}.${release}.tar.gz`.
The workflows will need trimming, because they also do signing, other architectures and store publishing. Run time is not measured; expect one to two hours for a full Windows build.

## 4. Your Windows PC

- **To run the client:** download the zip from the fork's release and install the Open Remote SSH fork (a VSIX). No toolchain is needed.
- **Optional, only to iterate on the client locally:** Node 24.18.0, Python 3, Git, and Visual Studio 2022 Build Tools with the "Desktop development with C++" workload and the Spectre-mitigated libraries. You'd want at least 16 GB of RAM and 30 to 40 GB of free disk. Note that a dev build (`scripts\code.bat`) has no commit id, so Open Remote SSH can't match a server to it. End-to-end SSH tests need a packaged build.

## 5. The Linux SSH host

- Any x64 distribution with glibc 2.28 or newer, `sshd`, `bash`, `wget` or `curl`, and outbound HTTPS to wherever the server tarballs are hosted. 2 GB of RAM is enough.
- WSL2 with sshd on the Windows PC is fine for a start. A small VM or VPS is closer to the real case, because the "close every window and the server stays up" test should run on a host that stays on.
- **Chosen host:** `ssh -p 2222 root@nas`, an Ubuntu 24.04 container on the NAS (x86_64, glibc 2.39, `dumb-init` as PID 1, about 37 GB of RAM available, 324 GB of disk free, reaches github.com). It passes all the checks above. Only Windows can reach it; the cloud container can't.
- To skip the download entirely, unpack a tarball into `~/.vscodium-server/bin/<commit>`. The setup script skips the download when the server is already there.

## 6. Do we need your fast storage?

**It isn't required.** A GitHub release on the public fork already gives the SSH host a URL it can download from.

**It helps with iteration speed.** Without it, every server change means a CI run before you can try it over SSH. With it, the container could build the server tarball and upload it, and the SSH host would fetch it within minutes. That only works if:
1. The container can reach it. This project uses the built-in cloud environment, which blocks unknown hosts. You would add a cloud environment in Project settings, under Environment, with your storage domain listed under allowed domains.
2. Writes work with a simple token, such as an HTTP PUT with a bearer token or an S3-compatible presigned URL. Reads must be anonymous HTTPS GET, because the SSH host fetches with plain `wget`.
3. The container can package the server tarball at all. Today it can't, because of the api.github.com 403 above. That needs a small local patch so the build downloads the built-in extensions from their direct release URLs.

So set it up only if you want that fast loop, after the patch in point 3 is in place.
