#!/bin/sh
# Minimal serial login shell for staging.

set -eu

expected_user="${DUT_SERIAL_USERNAME:-root}"
expected_password="${DUT_SERIAL_PASSWORD:-labgrid}"

while true; do
  printf "login: "
  if ! IFS= read -r user; then
    exit 0
  fi

  printf "Password: "
  if ! IFS= read -r password; then
    exit 0
  fi
  printf "\n"

  if [ "$user" != "$expected_user" ] || [ "$password" != "$expected_password" ]; then
    printf "Login incorrect\n\n"
    continue
  fi

  export HOME="/root"
  export USER="$expected_user"
  export LOGNAME="$expected_user"
  export PS1="# "
  exec /bin/bash -li
done
