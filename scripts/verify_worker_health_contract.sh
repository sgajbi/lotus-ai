#!/bin/sh
# Live proof of the worker-owned health contract (issue #369).
#
# Proves BOTH halves against a real Docker runtime, because a health signal that
# cannot fail is the defect this issue exists to remove:
#
#   1. the worker becomes healthy from its own evidence, with no HTTP server;
#   2. severing the required queue backend makes it unhealthy within the bound;
#   3. restoring the backend makes it healthy again.
#
# Exit 0 only when all three hold. Any unexpected state is a failure, including
# the worker never becoming healthy at all.
set -eu

# Git Bash rewrites container-absolute paths like /data/... into Windows paths
# before docker sees them, which made an earlier run of this script stop after
# step 2 while still reporting success. Disable that rewriting: a verification
# script that exits early and looks like a pass is the same defect it is here
# to catch.
MSYS_NO_PATHCONV=1
MSYS2_ARG_CONV_EXCL="*"
export MSYS_NO_PATHCONV MSYS2_ARG_CONV_EXCL

# Every stage sets its own flag; the final report requires all of them. An
# early exit therefore cannot print PASS.
reached_healthy=0
proved_no_http_port=0
reached_unhealthy=0
recovered=0

COMPOSE="docker compose"
WORKER="lotus-ai-worker"
HEALTHY_TIMEOUT="${HEALTHY_TIMEOUT:-180}"
UNHEALTHY_TIMEOUT="${UNHEALTHY_TIMEOUT:-120}"

health_state() {
    # `docker compose ps -q` omits exited containers, so a crashed worker used to
    # read as "no-container" - a real failure reported under a label that does
    # not say what happened. -a keeps it visible and the exit state is named,
    # because a worker that DIED is a different finding from one reporting
    # unhealthy, and this script must not let the two look alike.
    id=$($COMPOSE ps -aq "$WORKER" 2>/dev/null | head -1)
    if [ -z "$id" ]; then
        echo "no-container"
        return
    fi
    running=$(docker inspect --format '{{.State.Running}}' "$id")
    if [ "$running" != "true" ]; then
        echo "exited"
        return
    fi
    docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id"
}

wait_for_health() {
    want="$1"
    timeout="$2"
    label="$3"
    elapsed=0
    while [ "$elapsed" -lt "$timeout" ]; do
        current=$(health_state)
        if [ "$current" = "$want" ]; then
            echo "OK   $label: reached '$want' after ${elapsed}s"
            return 0
        fi
        if [ "$current" = "exited" ] && [ "$want" != "exited" ]; then
            echo "FAIL $label: the worker container EXITED. A dead worker is not"
            echo "     the same finding as an unhealthy one - the health contract"
            echo "     cannot report on a process that is gone."
            return 1
        fi
        sleep 5
        elapsed=$((elapsed + 5))
    done
    echo "FAIL $label: still '$(health_state)' after ${timeout}s, wanted '$want'"
    return 1
}

echo "=== 1. start the stack ==="
$COMPOSE up -d postgres redis lotus-ai "$WORKER"

echo "=== 2. the worker must become healthy from its own evidence ==="
wait_for_health healthy "$HEALTHY_TIMEOUT" "worker healthy"
reached_healthy=1

echo "--- the evidence it used (worker-owned, not an HTTP probe) ---"
$COMPOSE exec -T "$WORKER" python -m app.worker_health_main
$COMPOSE exec -T "$WORKER" cat /data/lotus-ai-worker-liveness.json
echo

echo "--- and the worker genuinely binds no HTTP port ---"
if $COMPOSE exec -T "$WORKER" python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
sys.exit(0 if s.connect_ex(('127.0.0.1', 8140)) != 0 else 1)
"; then
    echo "OK   worker binds no port 8140, so the inherited API probe could never pass"
    proved_no_http_port=1
else
    echo "FAIL worker is listening on 8140; the health contract is not worker-owned"
    exit 1
fi

echo "=== 3. sever the required queue backend ==="
$COMPOSE stop redis
wait_for_health unhealthy "$UNHEALTHY_TIMEOUT" "worker unhealthy after queue severed"
reached_unhealthy=1

echo "--- the reason must name the queue, not merely fail ---"
reason=$($COMPOSE exec -T "$WORKER" python -m app.worker_health_main || true)
echo "$reason"
case "$reason" in
    *WORKER_QUEUE_BACKEND_UNAVAILABLE*|*WORKER_LIVENESS_STALE*)
        echo "OK   refusal is attributable" ;;
    *)
        echo "FAIL unexpected reason code; health failed for a reason this test did not ask about"
        exit 1 ;;
esac

echo "=== 4. restore the backend and recover ==="
$COMPOSE start redis
wait_for_health healthy "$HEALTHY_TIMEOUT" "worker healthy after queue restored"
recovered=1

echo "=== 5. every stage must have run ==="
echo "healthy=$reached_healthy no_http_port=$proved_no_http_port unhealthy=$reached_unhealthy recovered=$recovered"
if [ "$reached_healthy" -ne 1 ] || [ "$proved_no_http_port" -ne 1 ]    || [ "$reached_unhealthy" -ne 1 ] || [ "$recovered" -ne 1 ]; then
    echo "FAIL not every stage ran; this is not a pass"
    exit 1
fi

echo
echo "PASS worker health is worker-owned, fails closed on a severed queue, and recovers."
