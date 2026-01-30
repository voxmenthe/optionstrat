#!/usr/bin/env bash
set -euo pipefail

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

info() {
  echo "[redis-setup] $*"
}

warn() {
  echo "[redis-setup] WARNING: $*" >&2
}

err() {
  echo "[redis-setup] ERROR: $*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

is_redis_running() {
  if ! have_cmd redis-cli; then
    return 1
  fi
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1
}

install_redis_macos() {
  if ! have_cmd brew; then
    err "Homebrew not found. Install from https://brew.sh and re-run."
    return 1
  fi
  info "Installing Redis via Homebrew..."
  brew install redis
}

install_redis_linux() {
  if have_cmd apt-get; then
    info "Installing Redis via apt-get..."
    sudo apt-get update
    sudo apt-get install -y redis-server
    return 0
  fi
  if have_cmd dnf; then
    info "Installing Redis via dnf..."
    sudo dnf install -y redis
    return 0
  fi
  if have_cmd yum; then
    info "Installing Redis via yum..."
    sudo yum install -y redis
    return 0
  fi
  if have_cmd pacman; then
    info "Installing Redis via pacman..."
    sudo pacman -S --noconfirm redis
    return 0
  fi
  if have_cmd zypper; then
    info "Installing Redis via zypper..."
    sudo zypper install -y redis
    return 0
  fi
  err "No supported package manager found. Install Redis manually and re-run."
  return 1
}

start_redis_macos() {
  if have_cmd brew; then
    info "Starting Redis via brew services..."
    brew services start redis >/dev/null
    return 0
  fi
  warn "brew services not available; falling back to redis-server."
  return 1
}

start_redis_linux() {
  if have_cmd systemctl; then
    if systemctl list-unit-files | grep -q '^redis.service'; then
      info "Starting Redis via systemctl (redis.service)..."
      sudo systemctl start redis
      return 0
    fi
    if systemctl list-unit-files | grep -q '^redis-server.service'; then
      info "Starting Redis via systemctl (redis-server.service)..."
      sudo systemctl start redis-server
      return 0
    fi
  fi
  if have_cmd service; then
    if service --status-all 2>/dev/null | grep -q 'redis-server'; then
      info "Starting Redis via service redis-server..."
      sudo service redis-server start
      return 0
    fi
    if service --status-all 2>/dev/null | grep -q 'redis'; then
      info "Starting Redis via service redis..."
      sudo service redis start
      return 0
    fi
  fi
  warn "No service manager detected; falling back to redis-server."
  return 1
}

start_redis_fallback() {
  if ! have_cmd redis-server; then
    err "redis-server is not available. Installation may have failed."
    return 1
  fi
  info "Starting Redis with redis-server --daemonize yes --port ${REDIS_PORT}..."
  redis-server --daemonize yes --port "$REDIS_PORT"
}

main() {
  if is_redis_running; then
    info "Redis is already running at ${REDIS_HOST}:${REDIS_PORT}."
    exit 0
  fi

  OS_NAME="$(uname -s)"
  case "$OS_NAME" in
    Darwin)
      if ! have_cmd redis-server; then
        install_redis_macos
      fi
      if ! start_redis_macos; then
        start_redis_fallback
      fi
      ;;
    Linux)
      if ! have_cmd redis-server; then
        install_redis_linux
      fi
      if ! start_redis_linux; then
        start_redis_fallback
      fi
      ;;
    *)
      err "Unsupported OS: $OS_NAME"
      exit 1
      ;;
  esac

  if is_redis_running; then
    info "Redis is running at ${REDIS_HOST}:${REDIS_PORT}."
    exit 0
  fi

  err "Redis did not start successfully."
  err "Try: redis-server --port ${REDIS_PORT}"
  err "Or check logs: tail -f /var/log/redis/redis-server.log"
  exit 1
}

main "$@"
