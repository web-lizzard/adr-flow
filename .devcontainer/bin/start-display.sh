#!/usr/bin/env bash
# Start virtual X display + VNC + noVNC for headed browsers inside the devcontainer.
# Open http://localhost:6080/vnc.html in your host browser (no host X server required).
set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-99}"
DISPLAY=":${DISPLAY_NUM}"
export DISPLAY
XVFB_PID_FILE="/tmp/xvfb-${DISPLAY_NUM}.pid"
VNC_PID_FILE="/tmp/x11vnc-${DISPLAY_NUM}.pid"
NOVNC_PID_FILE="/tmp/novnc-${DISPLAY_NUM}.pid"
WM_PID_FILE="/tmp/fluxbox-${DISPLAY_NUM}.pid"
LOG_DIR="/tmp/display-stack"
SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1920x1080x24}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_PORT="${VNC_PORT:-5900}"

mkdir -p "${LOG_DIR}"

is_running() {
	local pid_file="$1"
	[[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null
}

start_if_missing() {
	local name="$1"
	local pid_file="$2"
	shift 2
	if is_running "${pid_file}"; then
		return 0
	fi
	"$@" >>"${LOG_DIR}/${name}.log" 2>&1 &
	echo $! >"${pid_file}"
}

start_if_missing xvfb "${XVFB_PID_FILE}" \
	Xvfb "${DISPLAY}" -screen 0 "${SCREEN_GEOMETRY}" -ac +extension GLX +render -noreset

# Wait until the display socket exists.
for _ in $(seq 1 50); do
	if [[ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]]; then
		break
	fi
	sleep 0.1
done

if [[ ! -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]]; then
	echo "Failed to start Xvfb on ${DISPLAY}. See ${LOG_DIR}/xvfb.log" >&2
	exit 1
fi

start_if_missing fluxbox "${WM_PID_FILE}" \
	env DISPLAY="${DISPLAY}" fluxbox

start_if_missing x11vnc "${VNC_PID_FILE}" \
	x11vnc -display "${DISPLAY}" -forever -shared -rfbport "${VNC_PORT}" -nopw -noxdamage

start_if_missing novnc "${NOVNC_PID_FILE}" \
	websockify --web=/usr/share/novnc "${NOVNC_PORT}" "localhost:${VNC_PORT}"

echo "Display stack ready: DISPLAY=${DISPLAY}, noVNC http://localhost:${NOVNC_PORT}/vnc.html"
