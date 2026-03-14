#!/bin/bash
# Create user 'parking' with sudo on the remote server.
# Run as root. Password is passed as first argument (do not commit passwords to repo).
#
# Usage on server:
#   sudo bash create-parking-user.sh 'KortexDigital1342#'
# From your machine (copy script then run on server with password):
#   scp deploy/create-parking-user.sh root@185.229.226.37:/tmp/
#   ssh root@185.229.226.37 "sudo bash /tmp/create-parking-user.sh 'KortexDigital1342#'"

set -e
USERNAME="parking"
PASSWORD="${1:-}"

if [[ -z "$PASSWORD" ]]; then
  echo "Usage: sudo bash create-parking-user.sh '<password>'"
  echo "Example: sudo bash create-parking-user.sh 'KortexDigital1342#'"
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

if id "$USERNAME" &>/dev/null; then
  echo "User $USERNAME already exists. Setting password and ensuring sudo."
  echo "$USERNAME:$PASSWORD" | chpasswd
else
  echo "Creating user $USERNAME with home /opt/parking ..."
  useradd -m -d /opt/parking -s /bin/bash "$USERNAME"
  echo "$USERNAME:$PASSWORD" | chpasswd
fi

# Grant sudo (Ubuntu/Debian: group sudo)
if getent group sudo &>/dev/null; then
  usermod -aG sudo "$USERNAME"
  echo "Added $USERNAME to group sudo."
elif getent group wheel &>/dev/null; then
  usermod -aG wheel "$USERNAME"
  echo "Added $USERNAME to group wheel."
else
  echo "No sudo/wheel group found; adding to sudoers manually."
  echo "${USERNAME} ALL=(ALL) ALL" >> /etc/sudoers.d/parking
  chmod 440 /etc/sudoers.d/parking
fi

echo "Done. User $USERNAME can log in with: ssh $USERNAME@<server-ip>"
