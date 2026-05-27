#!/usr/bin/env bash
# GCE startup script: install Postgres, configure VPC access, enable backup cron.
set -euo pipefail

MARKER_DIR=/var/lib/adr-flow
MARKER_FILE="${MARKER_DIR}/postgres-ready"
LOG_FILE=/var/log/adr-flow-postgres-setup.log

exec >>"${LOG_FILE}" 2>&1
echo "=== adr-flow postgres setup $(date -Is) ==="

mkdir -p "${MARKER_DIR}"
rm -f "${MARKER_FILE}"

metadata_attr() {
	local key="$1"
	curl -sf -H "Metadata-Flavor: Google" \
		"http://metadata.google.internal/computeMetadata/v1/instance/attributes/${key}"
}

POSTGRES_PASSWORD="$(metadata_attr postgres-password)"
DB_NAME="$(metadata_attr db-name)"
DB_USER="$(metadata_attr db-user)"
CLOUD_RUN_SUBNET_RANGE="$(metadata_attr cloud-run-subnet-range)"
BACKUP_BUCKET="$(metadata_attr backup-bucket)"
POSTGRES_VERSION="$(metadata_attr postgres-version)"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql-"${POSTGRES_VERSION}" cron curl gnupg apt-transport-https ca-certificates
# gsutil for backup cron (VM service account has storage.objectCreator on backup bucket).
if ! command -v gsutil >/dev/null 2>&1; then
	install -d /usr/share/keyrings
	curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg |
		gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
	echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
		>/etc/apt/sources.list.d/google-cloud-sdk.list
	apt-get update -qq
	apt-get install -y -qq google-cloud-cli
fi

systemctl enable postgresql
systemctl start postgresql

PG_CONF="/etc/postgresql/${POSTGRES_VERSION}/main/postgresql.conf"
PG_HBA="/etc/postgresql/${POSTGRES_VERSION}/main/pg_hba.conf"

sed -i "s/^#*listen_addresses.*/listen_addresses = '*'/" "${PG_CONF}"
sed -i "s/^#*password_encryption.*/password_encryption = scram-sha-256/" "${PG_CONF}"

# Low connection limit for e2-micro; tune pool in app when DB code lands.
if grep -q '^max_connections' "${PG_CONF}"; then
	sed -i 's/^max_connections.*/max_connections = 20/' "${PG_CONF}"
else
	echo 'max_connections = 20' >>"${PG_CONF}"
fi

# Cloud Run Direct VPC subnet only (not 0.0.0.0/0).
if ! grep -q 'adr-flow-cloud-run' "${PG_HBA}"; then
	cat >>"${PG_HBA}" <<EOF

# adr-flow: Cloud Run Direct VPC egress
host    ${DB_NAME}    ${DB_USER}    ${CLOUD_RUN_SUBNET_RANGE}    scram-sha-256
EOF
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
	sudo -u postgres psql -v ON_ERROR_STOP=1 \
		-c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${POSTGRES_PASSWORD}';"
else
	sudo -u postgres psql -v ON_ERROR_STOP=1 \
		-c "ALTER ROLE ${DB_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';"
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
	sudo -u postgres psql -v ON_ERROR_STOP=1 \
		-c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 \
	-c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"

systemctl restart postgresql

# Daily pg_dump to GCS (VM SA needs storage.objectCreator on the bucket).
cat >/etc/cron.d/adr-flow-pg-backup <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
0 3 * * * postgres pg_dump -Fc ${DB_NAME} | gsutil cp - gs://${BACKUP_BUCKET}/\$(date +\%Y\%m\%d)-adrflow.dump
EOF
chmod 644 /etc/cron.d/adr-flow-pg-backup

touch "${MARKER_FILE}"
echo "=== postgres ready $(date -Is) ==="
