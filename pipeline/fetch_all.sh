#!/bin/bash
# Step 2 of the reproduction manual. Run from the folder that holds irs/ (it is created if missing).
# Downloads each IRS batch zip, keeps the returns that contain a Schedule H in irs/xml/, keeps the parent returns
# listed in NONH (no Schedule H; loaded for Part VII only, manual Section 6.5) in irs/xml_nonH/, logs each zip's
# SHA-256 and return count, and deletes the zip. Resumable: a done_ marker is left for each finished zip.
# Uses the system unzip (the IRS zips use Deflate64, which Python's zipfile cannot read) and works with the BSD tools
# on macOS as well as GNU tools. The largest IRS zips (2025 and 2026 batches 05A and 05B) carry a malformed
# end-of-archive record: unzip extracts every file and then exits with an error. So an unzip error is accepted only
# when every entry in the zip's directory was extracted at its recorded size (checked with Python's zipfile, which
# can read the directory but not the Deflate64 data).
set -u
mkdir -p irs; cd irs; mkdir -p xml xml_nonH logs
B2025="01A 02A 03A 04A 05A 05B 06A 07A 08A 09A 10A 11A 11B 11C 11D 12A"
B2026="01A 02A 03A 04A 05A 05B 06A 07A 08A"
NONH="202533219349327728"   # Advocate Health, Inc. (NC parent, EIN 88-4157429), batch 2025_TEOS_XML_11B
for y in 2025 2026; do
  if [ "$y" = 2025 ]; then L="$B2025"; else L="$B2026"; fi
  for b in $L; do
    z="${y}_TEOS_XML_${b}.zip"
    [ -f "done_${z}" ] && continue
    if [ ! -f "$z" ]; then
      curl -sS -f -m 1800 -L -o "$z.part" "https://apps.irs.gov/pub/epostcard/990/xml/$y/$z" && mv "$z.part" "$z" || { echo "DL FAIL $z"; continue; }
    fi
    echo "$(shasum -a 256 "$z")  $(wc -c < "$z" | tr -d ' ') bytes" >> logs/sha256.txt
    rm -rf tmp && mkdir tmp
    if ! unzip -q "$z" -d tmp > "logs/unzip_${z}.txt" 2>&1; then
      python3 -I -c '
import os, sys, zipfile
z, d = sys.argv[1:3]; e = zipfile.ZipFile(z).infolist()
bad = [i.filename for i in e if not os.path.isfile(os.path.join(d, i.filename)) or os.path.getsize(os.path.join(d, i.filename)) != i.file_size]
print(f"{len(e)} entries, {len(bad)} missing or short"); sys.exit(1 if bad else 0)' "$z" tmp >> "logs/unzip_${z}.txt" 2>&1 \
        || { echo "UNZIP FAIL $z (see logs/unzip_${z}.txt)"; continue; }
      echo "note $z: unzip reported an error after extracting every file; $(tail -1 "logs/unzip_${z}.txt")"
    fi
    find tmp -name '*.xml' | wc -l | tr -d ' ' > "logs/count_${z}.txt"
    find tmp -name '*.xml' -print0 | xargs -0 grep -l -m1 "<IRS990ScheduleH" > "logs/schH_${z}.txt"
    while IFS= read -r f; do mv "$f" xml/; done < "logs/schH_${z}.txt"
    for o in $NONH; do find tmp -name "${o}_public.xml" -exec mv {} xml_nonH/ \; ; done
    rm -rf tmp "$z"; touch "done_${z}"
    echo "done $z: $(cat "logs/count_${z}.txt") returns, $(wc -l < "logs/schH_${z}.txt" | tr -d ' ') with Schedule H"
  done
done
echo "xml/: $(ls xml | wc -l | tr -d ' ') files; xml_nonH/: $(ls xml_nonH | wc -l | tr -d ' ') files"
