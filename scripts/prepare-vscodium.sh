#!/usr/bin/env bash
# Apply VSCodium 1.140.06880 patches/product.json to vscodium/vscode (already checked out at
# the upstream commit) and run npm ci. Mirrors what vscodium/dev/build.sh + build.sh do before
# compiling, without the packaging steps.
#
# Run from Git Bash:  bash scripts/prepare-vscodium.sh

set -e

cd "$(dirname "$0")/../vscodium"

exec > >(tee ../prepare-vscodium.log) 2>&1

export APP_NAME="VSCodium"
export ASSETS_REPOSITORY="VSCodium/vscodium"
export BINARY_NAME="codium"
export CI_BUILD="no"
export GH_REPO_PATH="VSCodium/vscodium"
export ORG_NAME="VSCodium"
export SHOULD_BUILD="yes"
export VSCODE_QUALITY="stable"
export VSCODE_SKIP_NODE_VERSION_CHECK="yes"
export OS_NAME="windows"
export VSCODE_ARCH="x64"
export DISABLE_UPDATE="yes"
export MAX_OLD_SPACE_SIZE=8192

export MS_TAG="1.140.0"
export MS_COMMIT="07f806f999227108933c2e30515b26eecc1fda74"
export RELEASE_VERSION="1.140.06880"

. version.sh

echo "MS_TAG=\"${MS_TAG}\"" > dev/build.env
echo "MS_COMMIT=\"${MS_COMMIT}\"" >> dev/build.env
echo "RELEASE_VERSION=\"${RELEASE_VERSION}\"" >> dev/build.env
echo "BUILD_SOURCEVERSION=\"${BUILD_SOURCEVERSION}\"" >> dev/build.env

node --version
. prepare_vscode.sh

echo "prepare-vscodium: done"
