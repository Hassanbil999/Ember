"""Download the real NASA PSI experimental tables into data/raw/<dataset_id>/.

Usage (from the repo root):
    python scripts/fetch_psi.py               # fetch what is missing, verify what is there
    python scripts/fetch_psi.py --refresh     # re-download everything and compare with the pinned checksums
    python scripts/fetch_psi.py --only bass2 flex

Standard library only. Every file is checked against a pinned SHA-256:
  * a file already on disk is verified, never rewritten;
  * a download whose checksum differs is NOT written over the data. It is saved next to it as
    "<name>.psi-new" so a person can compare and decide (PSI may have corrected the table);
  * writes are atomic (temporary file, then rename), so an interrupted run never leaves half a CSV.
Writes data/raw/psi_manifest.json: where each file came from, its checksum, size, row count and
when it was retrieved. The provenance trail cites this file.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://psi.nasa.gov/geode-py/ws/studies/{acc}/download?file={name}"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
MANIFEST = RAW / "psi_manifest.json"
UA = "ember (NASA Space Apps 2026)"

# dataset_id, PSI accession, file name, pinned sha256 (verified against PSI on 2026-11-13)
TABLES = [
    # --- droplets (FLEX is the table the app already uses) ---
    ("flex", "PSI-69", "PSI-69_Experimental table_FLEX.csv", "37c88ce8ae9391b7544ff630a45ce87543d04d317cdbfbed104fe7d5c27e1b96"),
    ("flex2", "PSI-68", "PSI-68_Experimental table_Flex2.csv", "cc57ad1bd9977aa13e7ac6c3aa618303012686e232b36c052c6a9f1a74e5f528"),
    ("cfi", "PSI-39", "PSI-39_Experimental table_CFI.csv", "fb898e28762353aa132c16b886dbd207a024b1dd3c9bed5928d70d8036d2ec7e"),
    # --- solids: the habitat-relevant fire risk ---
    ("bass2", "PSI-25", "PSI-25_Experimental table_BASS-II.csv", "71e792bf6b5fb5ea620c5dd70fbbac05515992e12aefcf5dff47312caa48c042"),
    ("bass", "PSI-26", "PSI-26_Experimental table_BASS.csv", "ccfc3c54d948b64a1c5d2596a63c7c8019e51df0c91a1d62f039f48fa28c300f"),
    ("saffire1", "PSI-98", "PSI-98_Experimental table_SAFFIRE-1.csv", "c01f29c62455f0a3b512290ab85e5687ecded326733189f002f580368402308d"),
    ("saffire2", "PSI-99", "PSI-99_Experimental table_SAFFIRE-2.csv", "3c24390b9ef86f3d1ebaab911a1a3cc95a8759aebf42062371370e6d4b31b8ac"),
    ("saffire3", "PSI-100", "PSI-100_Experimental table_SAFFIRE-3.csv", "4d3c717ec20dd0247db670b2784a9fd7d746788bc54a936f80693e48eb8cd117"),
    # --- detection ---
    ("same", "PSI-102", "PSI-102_Experimental table_SAME.csv", "268d1e121d2f211b124407dd32b9475617bd269ede2c2d1749441da3e949a2af"),
    ("same_r", "PSI-101", "PSI-101_Experimental table_SAME-R.csv", "87164b7dc9168a4273c159f7a9f23699afbd06ad97b77974377e79b9bf8a3bef"),
    # --- gas flames (incl. high-oxygen tests relevant to a Moon base) ---
    ("acme_bre", "PSI-20", "PSI-20_Experimental table_ACME BRE.csv", "4aa5d3f98708ceacced5c620d46858b9965f8d4d941b203229f46467d53e5ab7"),
    ("cfig_normal", "PSI-159", "PSI-159_Experimental table_CFI-G_Normal Flames.csv", "d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a"),
    ("cfig_inverse", "PSI-159", "PSI-159_Experimental table_CFI-G_Inverse Flames.csv", "d4d44f8b9896936728748e34d1b6ad0812032a92fa5289599b708c138e3a9b39"),
    ("flame_design_normal", "PSI-10", "PSI-10_Experimental table_Flame Design_Normal Flame.csv", "4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb"),
    ("efield", "PSI-22", "PSI-22_Experimental table_ACME E-FIELD Flames.csv", "69090c357b83ae38d161d29001d1d32b40fd77b13324ca6585ee990cdceef524"),
    ("spice", "PSI-107", "PSI-107_Experimental table_Spice.csv", "fb0d7e60cf5367afb429089e9901d27288f78038efd26c8de1db4fbe04117136"),
    ("slice", "PSI-106", "PSI-106_Experimental table_Slice.csv", "89ef980810ca6d9aa8be817b42e36cd2adff23f5e9058361b5a33d18b4363f4d"),
    ("acme_cld", "PSI-21", "PSI-21_Experimental table_CLD Flame.csv", "9fafbc5b3dddaf715ce8025ed9154ce297803f7b69a935f077ec26c8249e44c0"),
    ("acme_sflame", "PSI-23", "PSI-23_Experimental table_ACME s-Flame.csv", "16cd10f50bd2e962887c8eb4077e5a9b3e790c78de8e0361c0b77e19300be7cf"),
]

# NASA documents quoted by the answer engine: (folder, file name, pinned sha256, source URL)
DOCUMENTS = [
    ("reports", "researchers_guide_combustion_science.pdf", "5fe046efe4e35e506023e27a9784d041e893026f19c9987591483614aea5d6b6",
     "https://www.nasa.gov/sites/default/files/atoms/files/np-2015-10-034-jsc_combustion_in_reduced_gravity-iss-mini-book-011116-508.pdf"),
    # outside NASA, shown apart from the PSI tests (config/external.yaml); CC BY-NC 4.0, Zenodo md5 ee54b6e4…
    ("external", "zarm_metal_barriers_index.csv", "77632b37f49260797f5cbb86b6e8bb40876801a482da38441b87e0e9e0afc6de",
     "https://zenodo.org/records/18479713/files/index.csv?download=1"),
]


def fetch_documents(refresh: bool) -> int:
    """Same rules as the tables: verify what is on disk, never overwrite with a file that differs."""
    problems = 0
    for folder, name, pinned, url in DOCUMENTS:
        out = RAW / folder / name
        if out.exists() and not refresh:
            ok = sha256(out.read_bytes()) == pinned
            print(f"{'OK  ' if ok else 'DIFF'}  doc      {name}  {'kept' if ok else 'on disk differs from the pinned checksum; left untouched'}")
            problems += not ok
            continue
        try:
            data = fetch(url)
        except Exception as e:
            print(f"FAIL  doc      {name}: {e}")
            problems += 1
            continue
        wrong_kind = not data.startswith(b"%PDF") if name.endswith(".pdf") else looks_like_html(data)
        if sha256(data) != pinned or wrong_kind:
            write_atomic(out.with_name(out.name + ".new"), data)
            print(f"DIFF  doc      {name}: NASA's file differs from the pinned checksum; saved as {name}.new for review")
            problems += 1
            continue
        write_atomic(out, data)
        print(f"OK    doc      {name}  downloaded")
    return problems


def url_of(acc: str, name: str) -> str:
    return BASE.format(acc=acc, name=urllib.parse.quote(name, safe=""))


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table_shape(data: bytes) -> tuple[int, list[str]]:
    """Data rows (non-blank, after the header) and the header row."""
    text = data.decode("utf-8-sig", errors="replace")
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    return max(len(rows) - 1, 0), (rows[0] if rows else [])


def looks_like_html(data: bytes) -> bool:
    head = data[:512].lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html") or b"<head" in head


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download files that are already on disk")
    ap.add_argument("--only", nargs="+", metavar="DATASET_ID", help="limit to these dataset ids")
    a = ap.parse_args(argv)

    known = {t[0] for t in TABLES}
    if a.only and (unknown := set(a.only) - known):
        print(f"unknown dataset id(s): {', '.join(sorted(unknown))}. Known: {', '.join(sorted(known))}")
        return 2

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    problems = 0

    for ds_id, acc, name, pinned in TABLES:
        if a.only and ds_id not in a.only:
            continue
        out = RAW / ds_id / name
        url = url_of(acc, name)
        local = out.read_bytes() if out.exists() else None

        if local is not None and not a.refresh:
            got = sha256(local)
            if got != pinned:
                print(f"DIFF  {acc:8} {ds_id:20} the file on disk differs from the pinned checksum ({got[:12]}…). "
                      f"Left untouched; run with --refresh --only {ds_id} to compare with PSI.")
                problems += 1
                continue
            data, status, retrieved = local, "kept", manifest.get(ds_id, {}).get("retrieved_utc")
        else:
            try:
                data = fetch(url)
            except Exception as e:  # network error, 404, TLS
                print(f"FAIL  {acc:8} {ds_id:20} {e}")
                problems += 1
                continue
            if looks_like_html(data):
                print(f"FAIL  {acc:8} {ds_id:20} PSI returned a web page, not a table. Nothing written.")
                problems += 1
                continue
            got = sha256(data)
            if got != pinned:
                side = out.with_name(out.name + ".psi-new")
                write_atomic(side, data)
                print(f"DIFF  {acc:8} {ds_id:20} PSI's file differs from the pinned checksum ({got[:12]}…). "
                      f"Saved as {side.name} for review; the data in use was not changed.")
                problems += 1
                continue
            if local != data:
                write_atomic(out, data)
            status, retrieved = "downloaded" if local is None else "verified", now

        rows, header = table_shape(data)
        manifest[ds_id] = {"psi_accession": acc, "file": name, "path": f"data/raw/{ds_id}/{name}", "url": url,
                           "sha256": pinned, "bytes": len(data), "data_rows": rows, "columns": len(header),
                           "retrieved_utc": retrieved or now}
        print(f"OK    {acc:8} {ds_id:20} {rows:4} rows  {status}")

    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n", encoding="utf-8")
    total = len(a.only) if a.only else len(TABLES)
    print(f"\n{total - problems}/{total} tables OK in {RAW}  (manifest: {MANIFEST.relative_to(RAW.parents[1])})")
    if not a.only:
        problems += fetch_documents(a.refresh)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
