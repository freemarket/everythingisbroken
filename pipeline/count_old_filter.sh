#!/bin/bash
# Counts, for every IRS batch fetch_all.sh uses, the returns the old filter kept (any file containing the text
# IRS990ScheduleH) and the returns the current filter keeps (files containing the element <IRS990ScheduleH).
# Written Nov 20, 2026 to test whether the 19,245 files once reported was the old filter's count (corrections log).
# Run from an empty folder; downloads each zip (about 7 GB in all), counts, deletes it. Prints one line per zip.
# Give zip names as arguments (e.g. 2025_TEOS_XML_11D.zip) to count only those.
set -u
B2025="01A 02A 03A 04A 05A 05B 06A 07A 08A 09A 10A 11A 11B 11C 11D 12A"
B2026="01A 02A 03A 04A 05A 05B 06A 07A 08A"
to=0; tn=0
ALL=""; for b in $B2025; do ALL="$ALL 2025_TEOS_XML_${b}.zip"; done; for b in $B2026; do ALL="$ALL 2026_TEOS_XML_${b}.zip"; done
[ $# -gt 0 ] && ALL="$*"
for z in $ALL; do
    y="${z:0:4}"
    curl -sS -f -m 1800 --retry 5 --retry-delay 15 --retry-all-errors -L -o "$z" "https://apps.irs.gov/pub/epostcard/990/xml/$y/$z" || { echo "DL FAIL $z"; continue; }
    rm -rf tmp && mkdir tmp && unzip -q "$z" -d tmp > /dev/null 2>&1   # 05A/05B end with a bad record after every file is out
    n=$(find tmp -name '*.xml' | wc -l | tr -d ' ')
    o=$(find tmp -name '*.xml' -print0 | xargs -0 grep -l -m1 "IRS990ScheduleH" | wc -l | tr -d ' ')
    h=$(find tmp -name '*.xml' -print0 | xargs -0 grep -l -m1 "<IRS990ScheduleH" | wc -l | tr -d ' ')
    to=$((to + o)); tn=$((tn + h)); echo "$z returns $n old_filter $o schedule_h $h"
    rm -rf tmp "$z"
done
echo "TOTAL old_filter $to schedule_h $tn"
