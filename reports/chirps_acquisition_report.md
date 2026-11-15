# CHIRPS Daily Precipitation Acquisition & Integrity Audit Report
**Regional Landslide Risk & Emergency Response Decision System (SIH26001)**  
**Milestone M1.3 / Data Engineering Verification**  
**Generated:** 2026-10-15  

---

## 1. Executive Summary

All **1,540 dates** comprising the exact mathematical union of 15-day antecedent rainfall windows ($t-14$ to $t$) for the 168 audited landslide events across Region A (Western Ghats) and Region B (Northeast India) have been successfully acquired, cropped, validated, and verified on disk.

```
Total Manifest Dates:     1,540 / 1,540  (100.0%)
Status = VALIDATED:       1,540 / 1,540  (100.0%)
Status = FAILED:              0 / 1,540  (0.0%)
Status = PENDING:             0 / 1,540  (0.0%)

Region A GeoTIFFs on disk: 1,540 / 1,540 (Validated, 0 corrupt)
Region B GeoTIFFs on disk: 1,540 / 1,540 (Validated, 0 corrupt)
Total GeoTIFF Crop Volume: 141.67 MB (148,548,400 bytes)
SHA-256 Checksum Mismatches: 0 across all 3,080 cropped rasters
Lingering .tmp / .part Files: 0
Preserved Raw .gz Archives: 12 (34.84 MB)
Test Suite Status:          118 / 118 passing
```

---

## 2. Recovery of the 4 Unreconciled Dates

During the high-throughput concurrent acquisition run, 1,536 dates completed end-to-end to `VALIDATED`. Four dates were held at intermediate states due to Windows atomic file-replace contention on the manifest:

| Date | Prior Status | Root Cause | Reconciliation Action | Final Status |
| :--- | :--- | :--- | :--- | :--- |
| **2009-09-16** | `DOWNLOADED` | Raw `.gz` downloaded (3.03 MB), but cropping worker encountered transient manifest write contention. | Decompressed raw `.gz` from local disk; sliced Region A & Region B GeoTIFF arrays; validated raster magic/shape/ranges; calculated SHA-256 digests; recorded in manifest. Zero network calls needed. | **VALIDATED** |
| **2012-05-25** | `CROPPED` | Both Region A & B crops generated on disk, but final checksum manifest update was interrupted by file lock. | Inspected and validated both existing GeoTIFF crops; verified non-null data; computed SHA-256 digests (`regionA`: `a1b02008...`, `regionB`: `7d1b3ea1...`); updated manifest. | **VALIDATED** |
| **2017-06-15** | `DOWNLOADED` | Raw `.gz` downloaded (3.12 MB), worker paused before crop write. | Decompressed raw `.gz` from local disk; cropped Region A & B; validated GeoTIFF integrity; calculated SHA-256 digests; recorded in manifest. Zero network calls needed. | **VALIDATED** |
| **2018-07-18** | `CROPPED` | Both Region A & B crops generated on disk; manifest update paused. | Validated existing Region A & B GeoTIFF crops; confirmed array shape and value bounds; computed SHA-256 digests (`regionA`: `e304856f...`, `regionB`: `1e506995...`); updated manifest. | **VALIDATED** |

---

## 3. Windows File Contention Resolution

### Root Cause
Under Windows filesystem semantics (specifically within cloud-synced folders such as OneDrive), rapid concurrent writes using a shared temporary file (`chirps_manifest.json.tmp`) resulted in `PermissionError: [WinError 5] Access is denied` when a background indexing or sync process held a transient read handle during `replace()`.

### Implementation Fix
In `src/data/chirps_downloader.py`:
1. **Thread/Process-Unique Staging Files**: Temp files now incorporate PID, thread ID, and nanosecond timestamp:
   ```python
   tmp = self.path.with_name(
       f"{self.path.stem}_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}.tmp"
   )
   ```
2. **Reentrant Lock Serialization**: Thread-level updates are serialized via `threading.RLock()`.
3. **Exponential Backoff on Windows Replace**: The atomic rename retries up to 10 times with exponential delay ($0.05 \times 2^k$ seconds) to gracefully wait out opportunistic file-locking handles:
   ```python
   max_attempts = 10
   for attempt in range(max_attempts):
       try:
           tmp.replace(self.path)
           break
       except PermissionError:
           if attempt == max_attempts - 1:
               raise
           time.sleep(0.05 * (2 ** attempt))
   ```
4. **Automated Cleanup**: Any unrenamed temporary file is cleanly removed on exception exit.
5. **Regression Test**: Added `test_m1_concurrent_manifest_updates_under_thread_pool` executing 30 parallel manifest updates across 8 concurrent worker threads, verifying 100% atomic write consistency with zero remaining `.tmp` artifacts.

---

## 4. Retained 12 `.gz` Archives Audit

A total of 12 raw `.gz` files (34.84 MB) are retained in `data/raw/rainfall/`:

| Filename | Size (Bytes) | Role During Execution | Necessity Analysis |
| :--- | :--- | :--- | :--- |
| `chirps-v2.0.2007.05.03.tif.gz` | 3,027,337 | Crops validated; raw file preserved by safety gate. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2007.07.10.tif.gz` | 3,148,820 | Crops validated; raw file preserved by safety gate. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2009.09.16.tif.gz` | 3,178,825 | Actively reused to generate Region A & B crops during recovery. | Redundant now that crops are verified. |
| `chirps-v2.0.2009.11.04.tif.gz` | 2,987,144 | Crops validated; raw file preserved by safety gate. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2012.05.25.tif.gz` | 3,061,643 | Crops already existed; preserved during recovery. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2016.06.06.tif.gz` | 3,059,510 | Crops validated; raw file preserved by safety gate. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2017.06.15.tif.gz` | 3,275,815 | Actively reused to generate Region A & B crops during recovery. | Redundant now that crops are verified. |
| `chirps-v2.0.2017.10.13.tif.gz` | 3,071,786 | Crops validated; raw file preserved by safety gate. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2018.05.13.tif.gz` | 2,897,975 | Crops validated; raw file preserved by safety gate. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2018.07.18.tif.gz` | 3,097,112 | Crops already existed; preserved during recovery. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2018.07.26.tif.gz` | 2,818,655 | Crops validated; raw file preserved by safety gate. | Redundant. Crops exist and pass validation. |
| `chirps-v2.0.2022.08.27.tif.gz` | 2,908,530 | Crops validated; raw file preserved by safety gate. | Redundant. Crops exist and pass validation. |

**Necessity Conclusion**:
All 12 `.gz` files have served their purpose. Their respective Region A and Region B `.tif` crops exist on disk, are fully validated, and their SHA-256 checksums match the manifest. The `.gz` files are preserved intact on disk pursuant to the user directive; they can be safely removed whenever disk space reclamation is requested.

---

## 5. Comprehensive 1,540-Date Integrity Audit

| Audit Dimension | Target / Expected | Actual Disk / Manifest Result | Status |
| :--- | :--- | :--- | :--- |
| **Total Manifest Entries** | 1,540 | 1,540 | **PASS** |
| **Unique Manifest Dates** | 1,540 | 1,540 (0 duplicates) | **PASS** |
| **Manifest Date Union** | Exactly matches 168 audited events $\times$ 15-day window | 1,540 dates (0 missing, 0 extraneous) | **PASS** |
| **Status = VALIDATED** | 1,540 | 1,540 (100.0%) | **PASS** |
| **Status = FAILED / PENDING** | 0 | 0 | **PASS** |
| **Region A Crops on Disk** | 1,540 | 1,540 files present | **PASS** |
| **Region B Crops on Disk** | 1,540 | 1,540 files present | **PASS** |
| **Crop Shape & Metadata** | Region A: $200 \times 80$, Region B: $80 \times 100$ | Exact pixel grid dimensions verified | **PASS** |
| **Crop Value Bounds** | Float32, $\ge 0.0$ mm (or $-9999.0$ nodata) | Validated for all 3,080 files | **PASS** |
| **SHA-256 Checksum Verification** | 100% bit-exact match against disk files | 3,080 / 3,080 match recorded checksums | **PASS** |
| **Checksum Mismatches** | 0 | 0 | **PASS** |
| **Partial / Incomplete Files (`.part`)** | 0 | 0 | **PASS** |
| **Lingering Temp Files (`*.tmp`)** | 0 | 0 | **PASS** |
| **Retained Raw `.gz` Files** | Preserved | 12 files (34.84 MB) | **PASS** |

---

## 6. Verification and Regression Testing

The full project test suite was executed:
- Total tests collected: 118
- Total passed: 118 (100%)
- Failures: 0
- Execution time: 6.63s

Tested components include:
- `tests/test_chirps_downloader.py`: Manifest schema, atomic I/O, integrity checkers, coordinate slicing, process pipeline, resume skip logic, retry exhaustion, completion reporting, and multithreaded concurrent save contention.
- `tests/test_uglc_audit.py`: Bounding box checks, date precision parsing, polygon inclusion, and UGLC Event 888497 audit.
- `tests/test_validation_scaffold.py`: Checks 01 through 12, CRS verification, catalog crosswalk, and configuration validation.
- `tests/test_ingestion.py`: Safe download and checksum routines.
