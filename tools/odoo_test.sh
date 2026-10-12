#!/usr/bin/env bash
# Install the modules in a real Odoo and run their Odoo tests (TransactionCase/HttpCase).
#
#   tools/odoo_test.sh <18|19|20> [base]
#
#   base   databank odoo_tvrep_<v>0: hr_timesheet + timeviking_timesheet_report
#
# Uses the test Odoo's of the main project (ODOO_BASE, default ../softwareservices-odoo-timesheets/var/odoo):
# <v>.0/venv, <v>.0/odoo (Community source) and <v>.0/tvreport.conf (our own addons path, databank and port).
# wkhtmltopdf: ODOO_BASE/wkhtml/bin is put in front of PATH when it exists. Runs under flock ODOO_BASE/.lock.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="${1:?version 18, 19 or 20}"; KIND="${2:-base}"
BASE="${ODOO_BASE:-$(cd "$ROOT/.." && pwd)/softwareservices-odoo-timesheets/var/odoo}"
CONF="$BASE/$V.0/tvreport.conf"
[ -f "$CONF" ] || { echo "no $CONF"; exit 2; }
[ -d "$BASE/wkhtml/bin" ] && export PATH="$BASE/wkhtml/bin:$PATH"
python3 "$ROOT/tools/build.py" dist "$V" >/dev/null
M=timeviking_timesheet_report
case "$KIND" in
  base) DB="odoo_tvrep_${V}0"; INSTALL="hr_timesheet,$M"; TAGS="/$M";;
  *) echo "unknown kind $KIND"; exit 2;;
esac
LOG="$BASE/$V.0/tvreport-$KIND.log"
rm -f "$LOG"
echo "Odoo $V.0, databank $DB: install/update $INSTALL and run $TAGS (log: $LOG)"
flock "$BASE/.lock" "$BASE/$V.0/venv/bin/python" "$BASE/$V.0/odoo/odoo-bin" -c "$CONF" -d "$DB" \
  -i "$INSTALL" -u $M --test-enable --test-tags "$TAGS" --stop-after-init --logfile "$LOG" || true
grep -E 'Ran [0-9]+ tests|[0-9]+ failed, [0-9]+ error|tests? (failed|errors?)|Starting .*Test|post-tests in' "$LOG" | tail -6 || true
fails="$(grep -cE ' (ERROR|CRITICAL) ' "$LOG" || true)"
if [ "$fails" != "0" ]; then echo "FAILED: $fails ERROR lines"; grep -E ' (ERROR|CRITICAL) ' "$LOG" | head -20; exit 1; fi
echo "Green: no ERROR lines in $LOG"
