"""Large-file check. Not part of the normal test run (the name does not start with test).

Makes a made-up delimited file of about 200 MB and one of about 1 GB, loads each in a
fresh process, and prints each process's peak memory. Passes when the 1 GB peak is
within 50 MB of the 200 MB peak. Deletes its files afterwards.

    python tests/large_file_check.py

Peak memory comes from GetProcessMemoryInfo, so this runs on Windows only.
"""

import ctypes
import json
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MB = 1024 * 1024
SIZES_MB = (200, 1000)
ALLOWED_GROWTH_MB = 50


def peak_working_set_bytes():
    """Peak working set of this process, via GetProcessMemoryInfo."""

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    c = Counters()
    c.cb = ctypes.sizeof(c)
    if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return c.PeakWorkingSetSize


def make_file(path, target_mb):
    """Made-up CSV: id, code, name, amount, day, note. Returns the row count."""
    target = target_mb * MB
    written = rows = 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("id,code,name,amount,day,note\n")
        while written < target:
            chunk = "".join(
                f"{i},K{i % 9973:05d},Name {i % 1237} of a made-up thing,{i % 1000}.{i % 100:02d},"
                f"2023-{i % 12 + 1:02d}-{i % 28 + 1:02d},some made-up free text {i % 311}\n"
                for i in range(rows, rows + 100_000)
            )
            f.write(chunk)
            written += len(chunk)
            rows += 100_000
    return rows


def write_dataset(folder):
    cols = {c: {"type": "text"} for c in ("id", "code", "name", "amount", "day", "note")}
    cfg = {
        "dataset": "large",
        "tables": {
            "big": {
                "source": {"path": "big.csv", "delimiter": ",", "header": True, "encoding": "utf-8"},
                "columns": cols,
            }
        },
    }
    (folder / "dataset.json").write_text(json.dumps(cfg), encoding="utf-8")


def child(dataset, runs):
    """Fresh process: load, then report this process's peak memory."""
    sys.path.insert(0, str(ROOT))
    from data_prepper import cli

    t0 = time.time()
    code = cli.main(["run", dataset, "--runs", runs])
    report = next(Path(runs).glob("*/*/reports/01-load.json"))
    loaded = json.loads(report.read_text(encoding="utf-8"))["tables"]["big"]["rows_loaded"]
    print(json.dumps({"exit": code, "rows_loaded": loaded, "peak_bytes": peak_working_set_bytes(),
                      "seconds": round(time.time() - t0, 1)}))
    return code


def main():
    if sys.platform != "win32":
        print("This check reads peak memory with GetProcessMemoryInfo, so it needs Windows.")
        return 2
    peaks = {}
    with tempfile.TemporaryDirectory(prefix="data_prepper_large_") as tmp:
        try:
            for size in SIZES_MB:
                folder = Path(tmp) / f"ds{size}"
                folder.mkdir()
                write_dataset(folder)
                rows = make_file(folder / "big.csv", size)
                actual = (folder / "big.csv").stat().st_size / MB
                print(f"{size} MB target: wrote {rows:,} rows, {actual:.0f} MB. Loading in a fresh process...", flush=True)
                p = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--child", str(folder), str(Path(tmp) / "runs")],
                    capture_output=True, text=True,
                )
                if p.returncode != 0:
                    print(p.stdout, p.stderr)
                    print("FAIL: the load did not finish with exit code 0")
                    return 1
                result = json.loads(p.stdout.strip().splitlines()[-1])
                if result["rows_loaded"] != rows:
                    print(f"FAIL: wrote {rows:,} rows but loaded {result['rows_loaded']:,}")
                    return 1
                peaks[size] = result["peak_bytes"] / MB
                print(f"  loaded {rows:,} rows; peak memory {peaks[size]:.1f} MB, {result['seconds']} s", flush=True)
                shutil.rmtree(folder)  # free the disk before the next size
                shutil.rmtree(Path(tmp) / "runs", ignore_errors=True)
        finally:
            pass  # TemporaryDirectory deletes everything left
    growth = peaks[SIZES_MB[1]] - peaks[SIZES_MB[0]]
    ok = growth <= ALLOWED_GROWTH_MB
    print(f"peak {SIZES_MB[0]} MB file: {peaks[SIZES_MB[0]]:.1f} MB; peak {SIZES_MB[1]} MB file: {peaks[SIZES_MB[1]]:.1f} MB; "
          f"difference {growth:.1f} MB (limit {ALLOWED_GROWTH_MB})")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        sys.exit(child(sys.argv[2], sys.argv[3]))
    sys.exit(main())
