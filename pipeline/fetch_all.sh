#!/bin/bash
set -u
cd irs; mkdir -p xml logs
B2025="01A 02A 03A 04A 05A 05B 06A 07A 08A 09A 10A 11A 11B 11C 11D 12A"
B2026="01A 02A 03A 04A 05A 05B 06A 07A 08A"
for y in 2025 2026; do
  if [ "$y" = 2025 ]; then L="$B2025"; else L="$B2026"; fi
  for b in $L; do
    z="${y}_TEOS_XML_${b}.zip"
    [ -f "done_${z}" ] && continue
    curl -sS -m 900 -L -o "$z" "https://apps.irs.gov/pub/epostcard/990/xml/$y/$z" || { echo "DL FAIL $z"; continue; }
    rm -rf tmp && mkdir tmp
    unzip -q "$z" -d tmp || { echo "UNZIP FAIL $z"; continue; }
    find tmp -name '*.xml' -print0 | xargs -0 grep -l -m1 "IRS990ScheduleH" > "logs/schH_${z}.txt"
    xargs -a "logs/schH_${z}.txt" -I{} mv {} xml/
    rm -rf tmp "$z"; touch "done_${z}"
  done
done
