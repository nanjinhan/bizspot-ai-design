from __future__ import annotations

import argparse
import io
import json
import logging
import math
import os
import re
import time
import warnings
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import yaml
from dotenv import load_dotenv
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import BallTree
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - optional dependency
    XGBClassifier = None

try:
    import lightgbm as lgb
except Exception:  # pragma: no cover - optional dependency
    lgb = None

try:
    import shap
except Exception:  # pragma: no cover - optional dependency
    shap = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOWNLOADS = Path.home() / "Downloads"
ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]
GWANGJU_SIGUNGU_CODES = ["29110", "29140", "29155", "29170", "29200"]
GWANGJU_SIGUNGU_NAMES = {
    "29110": "동구",
    "29140": "서구",
    "29155": "남구",
    "29170": "북구",
    "29200": "광산구",
}
GWANGJU_BOUNDS = {"lat_min": 34.9, "lat_max": 35.4, "lon_min": 126.5, "lon_max": 127.2}
LAT0 = 35.16
LON0 = 126.85
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = M_PER_DEG_LAT * math.cos(math.radians(LAT0))


def setup_logging() -> None:
    log_dir = PROJECT_ROOT / "outputs" / "reports"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8"),
        ],
        force=True,
    )


def ensure_dirs() -> None:
    for rel in [
        "config",
        "data/raw/D0_legal_dong_code",
        "data/raw/D1_store_info",
        "data/raw/D2_industry_code",
        "data/raw/D3_building_hub",
        "data/raw/D4_real_trade",
        "data/raw/D5_land_price",
        "data/raw/D6_transport",
        "data/raw/D7_subway",
        "data/raw/D8_floating_population",
        "data/api_cache/building",
        "data/api_cache/real_trade",
        "data/processed",
        "data/analysis",
        "outputs/reports",
        "outputs/figures",
        "outputs/tables",
        "web/data",
        "notebooks",
    ]:
        (PROJECT_ROOT / rel).mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    config_path = PROJECT_ROOT / "config" / "project_config.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(map(str, cols)) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        values = []
        for col in cols:
            value = row[col]
            if pd.isna(value):
                values.append("")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def bytes_from_path(path: Path, n: int = 128_000) -> bytes:
    with path.open("rb") as f:
        return f.read(n)


def detect_encoding_from_bytes(sample: bytes) -> str:
    last_error = None
    for enc in ENCODINGS:
        try:
            sample.decode(enc)
            return enc
        except Exception as exc:
            last_error = exc
    logging.debug("Encoding fallback to latin1 after %s", last_error)
    return "latin1"


def detect_csv_encoding_from_bytes(sample: bytes) -> str:
    newline = sample.rfind(b"\n")
    if newline > 0:
        sample = sample[: newline + 1]
    best_encoding = "latin1"
    best_score = -1
    first_success = None
    expected_terms = [
        "법정동",
        "공시지가",
        "상가",
        "상호",
        "위도",
        "경도",
        "정류장",
        "역사",
        "대분류",
        "소분류",
    ]
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(io.BytesIO(sample), encoding=enc, nrows=2)
            if first_success is None:
                first_success = enc
            columns_text = " ".join(map(str, df.columns))
            score = sum(term in columns_text for term in expected_terms)
            if score > best_score:
                best_score = score
                best_encoding = enc
        except Exception:
            continue
    if best_score > 0:
        return best_encoding
    return first_success or detect_encoding_from_bytes(sample)


def detect_encoding(path: Path) -> str:
    sample = bytes_from_path(path)
    if path.suffix.lower() == ".csv":
        return detect_csv_encoding_from_bytes(sample)
    return detect_encoding_from_bytes(sample)


def read_csv_auto(path: Path, **kwargs: Any) -> pd.DataFrame:
    last_error = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False, **kwargs)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"CSV read failed for {path}: {last_error}")


def read_csv_zip_entry(zip_path: Path, entry_name: str, **kwargs: Any) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(entry_name) as f:
            sample = f.read(128_000)
        encoding = detect_csv_encoding_from_bytes(sample)
        with zf.open(entry_name) as f:
            return pd.read_csv(f, encoding=encoding, low_memory=False, **kwargs)


def open_csv_zip_reader(zip_path: Path, entry_name: str, chunksize: int = 100_000):
    zf = zipfile.ZipFile(zip_path)
    f = zf.open(entry_name)
    sample = f.read(128_000)
    encoding = detect_csv_encoding_from_bytes(sample)
    f.close()
    f = zf.open(entry_name)
    reader = pd.read_csv(f, encoding=encoding, low_memory=False, chunksize=chunksize)
    return zf, f, reader, encoding


def clean_number(value: Any) -> float:
    if pd.isna(value):
        return np.nan
    text = str(value).replace(",", "").replace(" ", "").strip()
    if not text:
        return np.nan
    try:
        return float(text)
    except ValueError:
        return np.nan


def normalize_code(value: Any, length: int = 10) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    text = re.sub(r"\D", "", text)
    if not text:
        return ""
    return text.zfill(length)


def mode_or_blank(series: pd.Series) -> str:
    vals = [str(x) for x in series.dropna().tolist() if str(x).strip()]
    if not vals:
        return ""
    return Counter(vals).most_common(1)[0][0]


def in_gwangju_bbox(df: pd.DataFrame, lat_col: str = "lat", lon_col: str = "lon") -> pd.Series:
    return (
        df[lat_col].between(GWANGJU_BOUNDS["lat_min"], GWANGJU_BOUNDS["lat_max"])
        & df[lon_col].between(GWANGJU_BOUNDS["lon_min"], GWANGJU_BOUNDS["lon_max"])
    )


def lonlat_to_xy(lon: pd.Series | np.ndarray, lat: pd.Series | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lon_arr = np.asarray(lon, dtype=float)
    lat_arr = np.asarray(lat, dtype=float)
    x = (lon_arr - LON0) * M_PER_DEG_LON
    y = (lat_arr - LAT0) * M_PER_DEG_LAT
    return x, y


def xy_to_lonlat(x: pd.Series | np.ndarray, y: pd.Series | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    lon = x_arr / M_PER_DEG_LON + LON0
    lat = y_arr / M_PER_DEG_LAT + LAT0
    return lon, lat


def minmax_scale_safe(series: pd.Series, invert: bool = False) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        out = pd.Series(0.5, index=series.index)
    else:
        fill = s.median()
        s = s.fillna(fill)
        lo, hi = float(s.min()), float(s.max())
        if math.isclose(lo, hi):
            out = pd.Series(0.5, index=series.index)
        else:
            out = (s - lo) / (hi - lo)
    if invert:
        out = 1 - out
    return (out * 100).clip(0, 100)


def classify_industry_flags(df: pd.DataFrame) -> pd.DataFrame:
    text = (
        df.get("industry_l1_name", "").astype(str)
        + " "
        + df.get("industry_l2_name", "").astype(str)
        + " "
        + df.get("industry_l3_name", "").astype(str)
    )
    cafe_terms = ["커피", "카페", "다방", "비알코올", "음료"]
    food_terms = ["음식", "한식", "중식", "일식", "서양식", "분식", "치킨", "피자", "제과", "제빵", "베이커리", "식당"]
    convenience_terms = ["편의점"]
    life_terms = ["미용", "세탁", "약국", "학원", "의원", "병원", "생활", "수리", "스포츠", "문구", "서점"]
    df["is_cafe"] = text.str.contains("|".join(cafe_terms), case=False, regex=True).astype(int)
    df["is_food"] = text.str.contains("|".join(food_terms), case=False, regex=True).astype(int)
    df["is_convenience"] = text.str.contains("|".join(convenience_terms), case=False, regex=True).astype(int)
    df["is_life_service"] = text.str.contains("|".join(life_terms), case=False, regex=True).astype(int)
    return df


def list_source_files() -> list[Path]:
    candidates: list[Path] = []
    for root in [PROJECT_ROOT, PROJECT_ROOT / "data" / "raw", DOWNLOADS]:
        if root.exists():
            candidates.extend([p for p in root.rglob("*") if p.is_file()])
    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def inspect_zip_entries(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist()[:limit]:
                rows.append(
                    {
                        "name": info.filename,
                        "size": info.file_size,
                        "compressed_size": info.compress_size,
                    }
                )
    except Exception as exc:
        rows.append({"name": f"ZIP_READ_ERROR: {exc}", "size": None, "compressed_size": None})
    return rows


def find_zip_entry(path: Path, include_terms: list[str] | None = None, suffixes: tuple[str, ...] = (".csv", ".xlsx")) -> str | None:
    include_terms = include_terms or []
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
    except Exception:
        return None
    for name in names:
        lname = name.lower()
        if suffixes and not lname.endswith(suffixes):
            continue
        if all(term in name for term in include_terms):
            return name
    for name in names:
        if not suffixes or name.lower().endswith(suffixes):
            return name
    return None


def estimate_csv_rows_path(path: Path) -> int | None:
    try:
        with path.open("rb") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return None


def estimate_csv_rows_zip(path: Path, entry: str) -> int | None:
    try:
        with zipfile.ZipFile(path) as zf:
            with zf.open(entry) as f:
                return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return None


def inspect_columns(path: Path, dataset_id: str) -> tuple[str, list[str], int | None]:
    try:
        if path.suffix.lower() == ".csv":
            encoding = detect_encoding(path)
            df = pd.read_csv(path, encoding=encoding, nrows=5)
            return encoding, list(map(str, df.columns[:5])), estimate_csv_rows_path(path)
        if path.suffix.lower() == ".zip":
            entry = None
            if dataset_id == "D1":
                entry = find_zip_entry(path, ["광주"], (".csv",))
            elif dataset_id == "D5":
                entry = find_zip_entry(path, suffixes=(".csv",))
            elif dataset_id == "D0":
                entry = find_zip_entry(path, suffixes=(".xlsx", ".csv", ".txt"))
            else:
                entry = find_zip_entry(path)
            if entry and entry.lower().endswith(".csv"):
                with zipfile.ZipFile(path) as zf:
                    with zf.open(entry) as f:
                        sample = f.read(128_000)
                    encoding = detect_csv_encoding_from_bytes(sample)
                    with zf.open(entry) as f:
                        df = pd.read_csv(f, encoding=encoding, nrows=5)
                return f"{encoding} / zip:{entry}", list(map(str, df.columns[:5])), estimate_csv_rows_zip(path, entry)
            if entry and entry.lower().endswith(".xlsx"):
                with zipfile.ZipFile(path) as zf:
                    with zf.open(entry) as f:
                        df = pd.read_excel(f, nrows=5)
                return f"xlsx / zip:{entry}", list(map(str, df.columns[:5])), len(df)
        if path.suffix.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(path, nrows=5)
            return "xlsx", list(map(str, df.columns[:5])), len(df)
    except Exception as exc:
        return f"INSPECT_ERROR: {exc}", [], None
    return "", [], None


def infer_dataset_id(path: Path) -> str:
    name = path.name
    if "법정동코드" in name:
        return "D0"
    if "상가(상권)정보" in name and "업종코드" not in name and path.suffix.lower() == ".zip":
        return "D1"
    if "업종코드" in name:
        return "D2"
    if name.startswith("AL_D15"):
        return "D5"
    if "정류소" in name or "버스정류장" in name:
        return "D6"
    if "문화노선도" in name or "교통공사" in name:
        return "D7"
    if name == "BizSpot_AI_Codex_Master_Prompt_v6.md":
        return "PROMPT"
    return "UNKNOWN"


def scan_data() -> dict[str, Any]:
    logging.info("Scanning source files")
    ensure_dirs()
    files = list_source_files()
    useful = [p for p in files if infer_dataset_id(p) != "UNKNOWN"]
    scan_rows: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {"datasets": {}, "scan_generated_at": date.today().isoformat()}

    for path in sorted(useful, key=lambda p: (infer_dataset_id(p), p.name)):
        dataset_id = infer_dataset_id(path)
        encoding, columns, rows = inspect_columns(path, dataset_id)
        zip_entries = inspect_zip_entries(path, 12) if path.suffix.lower() == ".zip" else []
        coord_candidates = [c for c in columns if any(k in c.lower() for k in ["위도", "경도", "lat", "lon", "lng", "x", "y"])]
        address_candidates = [c for c in columns if "주소" in c or "위치" in c]
        date_candidates = [c for c in columns if "일자" in c or "연월" in c or "기준" in c]
        row = {
            "path": str(path),
            "name": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "dataset_id": dataset_id,
            "encoding": encoding,
            "is_zip": path.suffix.lower() == ".zip",
            "columns_first5": columns,
            "row_count_estimate": rows,
            "coord_column_candidates": coord_candidates,
            "address_column_candidates": address_candidates,
            "date_column_candidates": date_candidates,
            "usable": dataset_id != "UNKNOWN",
            "notes": "zip entries checked" if zip_entries else "",
            "zip_entries": zip_entries,
        }
        scan_rows.append(row)
        manifest["datasets"].setdefault(dataset_id, []).append(row)

    report_lines = [
        "# Data File Scan",
        "",
        "| Dataset | File | Size MB | Encoding | Rows est. | Columns first 5 | Notes |",
        "|---|---:|---:|---|---:|---|---|",
    ]
    for row in scan_rows:
        size_mb = row["size_bytes"] / (1024 * 1024)
        report_lines.append(
            f"| {row['dataset_id']} | `{row['name']}` | {size_mb:.2f} | {row['encoding']} | "
            f"{row['row_count_estimate'] or ''} | {', '.join(row['columns_first5'])} | {row['notes']} |"
        )
    report_lines.extend(
        [
            "",
            "## Zip Entries",
            "",
        ]
    )
    for row in scan_rows:
        if row["zip_entries"]:
            report_lines.append(f"### {row['name']}")
            for entry in row["zip_entries"]:
                report_lines.append(f"- `{entry['name']}` ({entry['size']} bytes)")
            report_lines.append("")

    write_yaml(PROJECT_ROOT / "config" / "data_manifest.yaml", manifest)
    (PROJECT_ROOT / "outputs" / "reports" / "data_file_scan.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )
    logging.info("Scan complete: %d mapped files", len(scan_rows))
    return manifest


def load_manifest() -> dict[str, Any]:
    path = PROJECT_ROOT / "config" / "data_manifest.yaml"
    if not path.exists():
        return scan_data()
    return read_yaml(path)


def select_manifest_file(manifest: dict[str, Any], dataset_id: str, name_contains: str | None = None) -> Path | None:
    rows = manifest.get("datasets", {}).get(dataset_id, [])
    paths = [Path(row["path"]) for row in rows if Path(row["path"]).exists()]
    if name_contains:
        paths = [p for p in paths if name_contains in p.name]
    if not paths:
        return None
    if dataset_id == "D1":
        non_dupes = [p for p in paths if "(1)" not in p.name]
        return sorted(non_dupes or paths, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def preprocess_legal_code(manifest: dict[str, Any]) -> pd.DataFrame:
    logging.info("Preprocessing D0 legal dong code")
    rows = manifest.get("datasets", {}).get("D0", [])
    frames: list[pd.DataFrame] = []
    for row in rows:
        path = Path(row["path"])
        if not path.exists():
            continue
        entry = find_zip_entry(path, suffixes=(".xlsx", ".csv", ".txt"))
        if path.suffix.lower() == ".zip" and entry:
            with zipfile.ZipFile(path) as zf:
                with zf.open(entry) as f:
                    if entry.lower().endswith(".xlsx"):
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            df = pd.read_excel(f)
                    else:
                        data = f.read()
                        encoding = detect_encoding_from_bytes(data[:128_000])
                        df = pd.read_csv(io.BytesIO(data), encoding=encoding)
        elif path.suffix.lower().endswith("xlsx"):
            df = pd.read_excel(path)
        else:
            continue
        frames.append(df)
    if not frames:
        out = pd.DataFrame(columns=["bjd_code", "sido_name", "sigungu_name", "dong_name", "full_bjd_name", "sigungu_code"])
    else:
        df = pd.concat(frames, ignore_index=True).drop_duplicates()
        code_col = "법정동코드"
        name_col = "법정동명"
        active_col = "폐지구분" if "폐지구분" in df.columns else "폐지여부" if "폐지여부" in df.columns else None
        df["bjd_code"] = df[code_col].map(lambda v: normalize_code(v, 10))
        df["sigungu_code"] = df["bjd_code"].str[:5]
        df["full_bjd_name"] = df[name_col].astype(str)
        if active_col:
            df = df[~df[active_col].astype(str).str.contains("폐지", na=False)]
        df = df[df["sigungu_code"].isin(GWANGJU_SIGUNGU_CODES)]
        parts = df["full_bjd_name"].str.split(" ", expand=True)
        df["sido_name"] = parts[0].fillna("광주광역시")
        df["sigungu_name"] = parts[1].fillna(df["sigungu_code"].map(GWANGJU_SIGUNGU_NAMES))
        df["dong_name"] = parts[2].fillna("")
        out = df[["bjd_code", "sido_name", "sigungu_name", "dong_name", "full_bjd_name", "sigungu_code"]].drop_duplicates()
    out_path = PROJECT_ROOT / "data" / "processed" / "legal_dong_gwangju.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    logging.info("D0 legal dong rows: %d", len(out))
    return out


def preprocess_store(manifest: dict[str, Any]) -> pd.DataFrame:
    logging.info("Preprocessing D1 store info")
    path = select_manifest_file(manifest, "D1")
    if path is None:
        raise FileNotFoundError("D1 store zip not found")
    entry = find_zip_entry(path, ["광주"], (".csv",))
    if not entry:
        raise FileNotFoundError(f"No Gwangju CSV entry in {path}")
    zf, f, reader, encoding = open_csv_zip_reader(path, entry, chunksize=100_000)
    chunks: list[pd.DataFrame] = []
    total_rows = 0
    try:
        for chunk in reader:
            total_rows += len(chunk)
            if "시도명" in chunk.columns:
                chunk = chunk[chunk["시도명"].astype(str).eq("광주광역시")]
            elif "지번주소" in chunk.columns:
                chunk = chunk[chunk["지번주소"].astype(str).str.contains("광주광역시", na=False)]
            chunks.append(chunk)
    finally:
        f.close()
        zf.close()
    if not chunks:
        raise RuntimeError("No store rows read")
    df = pd.concat(chunks, ignore_index=True)
    rename = {
        "상가업소번호": "store_id",
        "상호명": "store_name",
        "상권업종대분류코드": "industry_l1_code",
        "상권업종대분류명": "industry_l1_name",
        "상권업종중분류코드": "industry_l2_code",
        "상권업종중분류명": "industry_l2_name",
        "상권업종소분류코드": "industry_l3_code",
        "상권업종소분류명": "industry_l3_name",
        "시도명": "sido_name",
        "시군구코드": "sigungu_code",
        "시군구명": "sigungu_name",
        "행정동명": "admin_dong_name",
        "법정동코드": "bjd_code",
        "법정동명": "dong_name",
        "지번주소": "jibun_address",
        "도로명주소": "road_address",
        "경도": "lon",
        "위도": "lat",
    }
    df = df.rename(columns=rename)
    for col in rename.values():
        if col not in df.columns:
            df[col] = ""
    before = len(df)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    missing_coord = int(df[["lat", "lon"]].isna().any(axis=1).sum())
    df = df.dropna(subset=["lat", "lon"])
    outside_bbox = int((~in_gwangju_bbox(df)).sum())
    df = df[in_gwangju_bbox(df)]
    df["bjd_code"] = df["bjd_code"].map(lambda v: normalize_code(v, 10))
    df["sigungu_code"] = df["sigungu_code"].map(lambda v: normalize_code(v, 5)[-5:] if normalize_code(v, 5) else "")
    df.loc[df["sigungu_code"].eq(""), "sigungu_code"] = df.loc[df["sigungu_code"].eq(""), "bjd_code"].str[:5]
    df = df[df["sigungu_code"].isin(GWANGJU_SIGUNGU_CODES)]
    df = classify_industry_flags(df)
    df["geometry_wkt"] = "POINT(" + df["lon"].astype(str) + " " + df["lat"].astype(str) + ")"
    duplicated = int(df.duplicated(subset=["store_id"]).sum()) if "store_id" in df.columns else 0
    df = df.drop_duplicates(subset=["store_id"], keep="first")
    keep = [
        "store_id",
        "store_name",
        "industry_l1_code",
        "industry_l1_name",
        "industry_l2_code",
        "industry_l2_name",
        "industry_l3_code",
        "industry_l3_name",
        "sido_name",
        "sigungu_code",
        "sigungu_name",
        "admin_dong_name",
        "bjd_code",
        "dong_name",
        "road_address",
        "jibun_address",
        "lon",
        "lat",
        "geometry_wkt",
        "is_food",
        "is_cafe",
        "is_convenience",
        "is_life_service",
    ]
    df = df[keep].copy()
    out_path = PROJECT_ROOT / "data" / "processed" / "store_gwangju.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    quality = {
        "source_zip": str(path),
        "source_entry": entry,
        "encoding": encoding,
        "source_rows_read": total_rows,
        "gwangju_rows_before_coord_filter": before,
        "missing_coord_rows": missing_coord,
        "outside_bbox_rows": outside_bbox,
        "duplicate_store_id_rows": duplicated,
        "final_rows": len(df),
    }
    write_json(PROJECT_ROOT / "outputs" / "tables" / "store_quality.json", quality)
    logging.info("D1 store rows: %d", len(df))
    return df


def preprocess_industry(manifest: dict[str, Any]) -> pd.DataFrame:
    logging.info("Preprocessing D2 industry code")
    path = select_manifest_file(manifest, "D2")
    if path is None:
        out = pd.DataFrame()
    else:
        df = read_csv_auto(path)
        rename = {
            "대분류코드": "industry_l1_code",
            "대분류명": "industry_l1_name",
            "중분류코드": "industry_l2_code",
            "중분류명": "industry_l2_name",
            "소분류코드": "industry_l3_code",
            "소분류명": "industry_l3_name",
        }
        df = df.rename(columns=rename)
        out = classify_industry_flags(df)
    out_path = PROJECT_ROOT / "data" / "processed" / "industry_code.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    logging.info("D2 industry rows: %d", len(out))
    return out


def preprocess_land_price(manifest: dict[str, Any]) -> pd.DataFrame:
    logging.info("Preprocessing D5 land price")
    rows = manifest.get("datasets", {}).get("D5", [])
    csv_zips = [Path(r["path"]) for r in rows if Path(r["path"]).name.startswith("AL_D151")]
    if not csv_zips:
        out = pd.DataFrame()
        out.to_csv(PROJECT_ROOT / "data" / "processed" / "land_price_gwangju.csv", index=False, encoding="utf-8-sig")
        return out
    path = sorted(csv_zips, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    entry = find_zip_entry(path, suffixes=(".csv",))
    if not entry:
        raise FileNotFoundError(f"No CSV entry in {path}")
    zf, f, reader, _ = open_csv_zip_reader(path, entry, chunksize=300_000)
    chunks: list[pd.DataFrame] = []
    try:
        for chunk in reader:
            if "법정동코드" not in chunk.columns:
                continue
            chunk["bjd_code"] = chunk["법정동코드"].map(lambda v: normalize_code(v, 10))
            chunk["sigungu_code"] = chunk["bjd_code"].str[:5]
            chunk = chunk[chunk["sigungu_code"].isin(GWANGJU_SIGUNGU_CODES)]
            if chunk.empty:
                continue
            chunk["land_price_per_m2"] = chunk["공시지가"].map(clean_number) if "공시지가" in chunk.columns else np.nan
            chunk["sigungu_name"] = chunk["sigungu_code"].map(GWANGJU_SIGUNGU_NAMES)
            keep = [
                "bjd_code",
                "sigungu_code",
                "sigungu_name",
                "법정동명",
                "지번",
                "기준연도",
                "기준월",
                "land_price_per_m2",
                "공시일자",
            ]
            keep = [c for c in keep if c in chunk.columns]
            chunks.append(chunk[keep])
    finally:
        f.close()
        zf.close()
    out = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    if not out.empty:
        out["land_price_quantile"] = pd.qcut(
            out["land_price_per_m2"].rank(method="first"), 10, labels=False, duplicates="drop"
        ) + 1
        out["land_price_grade"] = out["land_price_quantile"]
    out_path = PROJECT_ROOT / "data" / "processed" / "land_price_gwangju.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    if out.empty:
        summary = pd.DataFrame()
    else:
        summary = (
            out.groupby(["bjd_code", "sigungu_code", "sigungu_name", "법정동명"], dropna=False)
            .agg(
                avg_land_price_dong=("land_price_per_m2", "mean"),
                median_land_price_dong=("land_price_per_m2", "median"),
                land_price_count=("land_price_per_m2", "size"),
            )
            .reset_index()
        )
    summary.to_csv(PROJECT_ROOT / "data" / "processed" / "land_price_dong_summary.csv", index=False, encoding="utf-8-sig")
    logging.info("D5 land price rows: %d, dong summary rows: %d", len(out), len(summary))
    return out


def preprocess_transport(manifest: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    logging.info("Preprocessing D6/D7 transport")
    rows = manifest.get("datasets", {}).get("D6", [])
    gj_path = next((Path(r["path"]) for r in rows if "정류소" in Path(r["path"]).name), None)
    nat_path = next((Path(r["path"]) for r in rows if "버스정류장" in Path(r["path"]).name), None)
    bus = pd.DataFrame()
    local_rows = 0
    local_has_coords = False
    if gj_path and gj_path.exists():
        local = read_csv_auto(gj_path)
        local_rows = len(local)
        local_has_coords = {"위도", "경도"}.issubset(local.columns)
        if local_has_coords:
            bus = local.rename(columns={"정류소명": "stop_name", "위도": "lat", "경도": "lon", "자치구": "sigungu_name"})
    if bus.empty and nat_path and nat_path.exists():
        chunks = []
        for chunk in pd.read_csv(nat_path, encoding=detect_encoding(nat_path), chunksize=200_000, low_memory=False):
            chunk["lat"] = pd.to_numeric(chunk.get("위도"), errors="coerce")
            chunk["lon"] = pd.to_numeric(chunk.get("경도"), errors="coerce")
            mask_name = (
                chunk.get("도시명", pd.Series("", index=chunk.index)).astype(str).str.contains("광주", na=False)
                | chunk.get("관리도시명", pd.Series("", index=chunk.index)).astype(str).str.contains("광주", na=False)
            )
            mask_bbox = in_gwangju_bbox(chunk, "lat", "lon")
            chunk = chunk[mask_name | mask_bbox]
            if not chunk.empty:
                chunks.append(chunk)
        if chunks:
            bus = pd.concat(chunks, ignore_index=True).rename(
                columns={"정류장번호": "stop_id", "정류장명": "stop_name", "도시명": "city_name", "관리도시명": "manager_city_name"}
            )
    if not bus.empty:
        for col in ["stop_id", "stop_name", "city_name", "manager_city_name"]:
            if col not in bus.columns:
                bus[col] = ""
        bus["lat"] = pd.to_numeric(bus["lat"], errors="coerce")
        bus["lon"] = pd.to_numeric(bus["lon"], errors="coerce")
        bus = bus.dropna(subset=["lat", "lon"])
        bus = bus[in_gwangju_bbox(bus)]
        bus = bus.drop_duplicates(subset=["lat", "lon", "stop_name"])
        bus = bus[["stop_id", "stop_name", "city_name", "manager_city_name", "lon", "lat"]]
    bus.to_csv(PROJECT_ROOT / "data" / "processed" / "transport_bus_gwangju.csv", index=False, encoding="utf-8-sig")
    transport_quality = {
        "local_bus_rows": local_rows,
        "local_bus_has_coordinates": local_has_coords,
        "final_bus_rows": len(bus),
        "fallback_used": bool(not local_has_coords and nat_path),
    }
    write_json(PROJECT_ROOT / "outputs" / "tables" / "transport_quality.json", transport_quality)

    subway_path = select_manifest_file(manifest, "D7")
    subway = pd.DataFrame()
    if subway_path and subway_path.exists():
        df = read_csv_auto(subway_path)
        rename = {
            "역번호": "station_id",
            "역사명": "station_name",
            "노선명": "line_name",
            "역위도": "lat",
            "역경도": "lon",
            "역사도로명주소": "road_address",
        }
        subway = df.rename(columns=rename)
        for col in ["station_id", "station_name", "line_name", "lat", "lon", "road_address"]:
            if col not in subway.columns:
                subway[col] = ""
        subway["lat"] = pd.to_numeric(subway["lat"], errors="coerce")
        subway["lon"] = pd.to_numeric(subway["lon"], errors="coerce")
        subway = subway.dropna(subset=["lat", "lon"])
        subway = subway[in_gwangju_bbox(subway)]
        subway = subway[["station_id", "station_name", "line_name", "lon", "lat", "road_address"]]
    subway.to_csv(PROJECT_ROOT / "data" / "processed" / "subway_gwangju.csv", index=False, encoding="utf-8-sig")
    logging.info("D6 bus rows: %d, D7 subway rows: %d", len(bus), len(subway))
    return bus, subway


def parse_api_items(payload: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(payload)
        body = data.get("response", {}).get("body", {})
        items = body.get("items", {})
        if isinstance(items, dict):
            item = items.get("item", [])
        else:
            item = items
        if isinstance(item, dict):
            return [item]
        if isinstance(item, list):
            return item
        return []
    except Exception:
        pass
    try:
        root = ElementTree.fromstring(payload.encode("utf-8"))
        result_code = root.findtext(".//resultCode")
        if result_code and result_code not in {"00", "000"}:
            logging.debug("API result code %s: %s", result_code, root.findtext(".//resultMsg"))
        items = []
        for item in root.findall(".//item"):
            items.append({child.tag: child.text for child in list(item)})
        return items
    except Exception:
        return []


def request_public_api(url: str, params: dict[str, Any], timeout: int = 20) -> tuple[str, int, str]:
    response = requests.get(url, params=params, timeout=timeout)
    return response.text, response.status_code, response.url


def collect_real_trade_api(config: dict[str, Any]) -> pd.DataFrame:
    logging.info("Collecting optional D4 real trade API")
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
    out_path = PROJECT_ROOT / "data" / "processed" / "real_trade_gwangju.csv"
    if not key:
        logging.warning("DATA_GO_KR_SERVICE_KEY is not set. Skipping D4 API.")
        pd.DataFrame().to_csv(out_path, index=False, encoding="utf-8-sig")
        return pd.DataFrame()

    api_cfg = config.get("api", {})
    start_year = int(api_cfg.get("start_year", 2020))
    end_year = int(api_cfg.get("end_year", 2026))
    timeout = int(api_cfg.get("timeout_sec", 20))
    sleep_sec = float(api_cfg.get("sleep_sec", 0.08))
    months = []
    today = date.today()
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if year > today.year or (year == today.year and month > today.month):
                continue
            months.append(f"{year}{month:02d}")
    max_months = int(api_cfg.get("max_real_trade_months", 0) or 0)
    if max_months > 0:
        months = months[:max_months]
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade"
    cache_dir = PROJECT_ROOT / "data" / "api_cache" / "real_trade"
    cache_dir.mkdir(parents=True, exist_ok=True)
    all_items: list[dict[str, Any]] = []
    hard_failures = 0
    for lawd in GWANGJU_SIGUNGU_CODES:
        for ym in months:
            cache = cache_dir / f"{lawd}_{ym}.json"
            if cache.exists():
                payload = cache.read_text(encoding="utf-8")
            else:
                params = {
                    "serviceKey": key,
                    "LAWD_CD": lawd,
                    "DEAL_YMD": ym,
                    "pageNo": 1,
                    "numOfRows": 1000,
                    "_type": "json",
                }
                try:
                    payload, status, _ = request_public_api(url, params, timeout=timeout)
                    cache.write_text(payload, encoding="utf-8")
                    if status >= 400:
                        hard_failures += 1
                except Exception as exc:
                    logging.warning("D4 API request failed %s %s: %s", lawd, ym, exc)
                    hard_failures += 1
                    continue
                time.sleep(sleep_sec)
            items = parse_api_items(payload)
            for item in items:
                item["sigungu_code"] = lawd
                item["deal_ym"] = ym
            all_items.extend(items)
        if hard_failures > 5 and not all_items:
            logging.warning("D4 API appears unavailable. Stopping optional collection early.")
            break
    df = pd.DataFrame(all_items)
    if df.empty:
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        return df
    amount_col = next((c for c in ["dealAmount", "거래금액", "dealAmt"] if c in df.columns), None)
    area_col = next((c for c in ["excluUseAr", "전용면적", "area"] if c in df.columns), None)
    dong_col = next((c for c in ["umdNm", "법정동", "dong"] if c in df.columns), None)
    if amount_col:
        df["trade_price"] = df[amount_col].map(clean_number)
    else:
        df["trade_price"] = np.nan
    if area_col:
        df["trade_area"] = df[area_col].map(clean_number)
    else:
        df["trade_area"] = np.nan
    df["trade_price_per_area"] = np.where(df["trade_area"] > 0, df["trade_price"] / df["trade_area"], np.nan)
    df["sigungu_name"] = df["sigungu_code"].map(GWANGJU_SIGUNGU_NAMES)
    if dong_col:
        df["dong_name"] = df[dong_col].astype(str).str.strip()
    else:
        df["dong_name"] = ""
    summary = (
        df.groupby(["sigungu_code", "sigungu_name", "dong_name"], dropna=False)
        .agg(
            trade_price_median_dong=("trade_price", "median"),
            trade_price_per_area_median_dong=("trade_price_per_area", "median"),
            commercial_trade_count_dong=("trade_price", "size"),
        )
        .reset_index()
    )
    summary["cost_proxy_trade"] = summary["trade_price_per_area_median_dong"].fillna(summary["trade_price_median_dong"])
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    summary.to_csv(PROJECT_ROOT / "data" / "processed" / "real_trade_dong_summary.csv", index=False, encoding="utf-8-sig")
    logging.info("D4 real trade rows: %d, summary rows: %d", len(df), len(summary))
    return df


def collect_building_api(config: dict[str, Any]) -> pd.DataFrame:
    logging.info("Collecting optional D3 building registry API")
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
    out_path = PROJECT_ROOT / "data" / "processed" / "building_gwangju.csv"
    if not key:
        logging.warning("DATA_GO_KR_SERVICE_KEY is not set. Skipping D3 API.")
        pd.DataFrame().to_csv(out_path, index=False, encoding="utf-8-sig")
        return pd.DataFrame()
    legal_path = PROJECT_ROOT / "data" / "processed" / "legal_dong_gwangju.csv"
    if not legal_path.exists():
        pd.DataFrame().to_csv(out_path, index=False, encoding="utf-8-sig")
        return pd.DataFrame()
    legal = pd.read_csv(legal_path, dtype=str)
    dongs = legal[legal["bjd_code"].str.endswith("00") == False].copy()  # noqa: E712
    api_cfg = config.get("api", {})
    max_dongs = int(api_cfg.get("max_building_dongs", 25))
    max_pages = int(api_cfg.get("max_building_pages_per_dong", 1))
    num_rows = int(api_cfg.get("num_rows", 100))
    timeout = int(api_cfg.get("timeout_sec", 20))
    sleep_sec = float(api_cfg.get("sleep_sec", 0.08))
    url = "https://apis.data.go.kr/1613000/BldRgstService_v2/getBrTitleInfo"
    cache_dir = PROJECT_ROOT / "data" / "api_cache" / "building"
    cache_dir.mkdir(parents=True, exist_ok=True)
    all_items: list[dict[str, Any]] = []
    failures = 0
    for _, row in dongs.head(max_dongs).iterrows():
        bjd = str(row["bjd_code"])
        sigungu_cd = bjd[:5]
        bjdong_cd = bjd[5:]
        for page in range(1, max_pages + 1):
            cache = cache_dir / f"{sigungu_cd}_{bjdong_cd}_{page}.json"
            if cache.exists():
                payload = cache.read_text(encoding="utf-8")
            else:
                params = {
                    "serviceKey": key,
                    "sigunguCd": sigungu_cd,
                    "bjdongCd": bjdong_cd,
                    "pageNo": page,
                    "numOfRows": num_rows,
                    "_type": "json",
                }
                try:
                    payload, status, _ = request_public_api(url, params, timeout=timeout)
                    cache.write_text(payload, encoding="utf-8")
                    if status >= 400:
                        failures += 1
                except Exception as exc:
                    logging.warning("D3 API request failed %s %s: %s", sigungu_cd, bjdong_cd, exc)
                    failures += 1
                    continue
                time.sleep(sleep_sec)
            items = parse_api_items(payload)
            for item in items:
                item["bjd_code"] = bjd
                item["sigungu_code"] = sigungu_cd
                item["dong_name"] = row.get("dong_name", "")
            all_items.extend(items)
        if failures > 5 and not all_items:
            logging.warning("D3 API appears unavailable. Stopping optional collection early.")
            break
    df = pd.DataFrame(all_items)
    if df.empty:
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        return df
    use_col = next((c for c in ["mainPurpsCdNm", "주용도명", "etcPurps"] if c in df.columns), None)
    area_col = next((c for c in ["totArea", "연면적", "archArea"] if c in df.columns), None)
    floor_col = next((c for c in ["grndFlrCnt", "지상층수"] if c in df.columns), None)
    under_col = next((c for c in ["ugrndFlrCnt", "지하층수"] if c in df.columns), None)
    date_col = next((c for c in ["useAprDay", "사용승인일"] if c in df.columns), None)
    df["main_use_name"] = df[use_col].astype(str) if use_col else ""
    df["gross_floor_area"] = df[area_col].map(clean_number) if area_col else np.nan
    df["ground_floor_count"] = df[floor_col].map(clean_number) if floor_col else np.nan
    df["underground_floor_count"] = df[under_col].map(clean_number) if under_col else np.nan
    if date_col:
        year = pd.to_numeric(df[date_col].astype(str).str.slice(0, 4), errors="coerce")
        df["building_age"] = date.today().year - year
    else:
        df["building_age"] = np.nan
    df["commercial_building_flag"] = df["main_use_name"].str.contains("근린|판매|업무|상업|음식|소매", regex=True, na=False).astype(int)
    df["sigungu_name"] = df["sigungu_code"].map(GWANGJU_SIGUNGU_NAMES)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    summary = (
        df.groupby(["bjd_code", "sigungu_code", "sigungu_name", "dong_name"], dropna=False)
        .agg(
            building_age_avg_dong=("building_age", "mean"),
            gross_floor_area_avg_dong=("gross_floor_area", "mean"),
            commercial_building_ratio_dong=("commercial_building_flag", "mean"),
            building_count_dong=("commercial_building_flag", "size"),
        )
        .reset_index()
    )
    summary.to_csv(PROJECT_ROOT / "data" / "processed" / "building_dong_summary.csv", index=False, encoding="utf-8-sig")
    logging.info("D3 building rows: %d, summary rows: %d", len(df), len(summary))
    return df


def preprocess_all() -> None:
    manifest = load_manifest()
    config = load_config()
    preprocess_legal_code(manifest)
    preprocess_store(manifest)
    preprocess_industry(manifest)
    preprocess_land_price(manifest)
    preprocess_transport(manifest)
    if config.get("optional_data", {}).get("use_real_trade_api", True):
        collect_real_trade_api(config)
    if config.get("optional_data", {}).get("use_building_api", True):
        collect_building_api(config)


def add_accessibility_features(candidates: pd.DataFrame, points: pd.DataFrame, prefix: str, radii: list[int]) -> pd.DataFrame:
    if points.empty or candidates.empty:
        candidates[f"nearest_{prefix}_m"] = np.nan
        for r in radii:
            candidates[f"{prefix}_count_{r}m"] = 0
        return candidates
    px, py = lonlat_to_xy(points["lon"], points["lat"])
    cx, cy = lonlat_to_xy(candidates["lon"], candidates["lat"])
    point_xy = np.column_stack([px, py])
    cand_xy = np.column_stack([cx, cy])
    tree = BallTree(point_xy, metric="euclidean")
    dist, _ = tree.query(cand_xy, k=1)
    candidates[f"nearest_{prefix}_m"] = dist[:, 0]
    for r in radii:
        counts = tree.query_radius(cand_xy, r=r, count_only=True)
        candidates[f"{prefix}_count_{r}m"] = counts
    return candidates


def build_features() -> pd.DataFrame:
    logging.info("Building grid features")
    config = load_config()
    grid_size = int(config.get("analysis", {}).get("grid_size_m", 500))
    store_path = PROJECT_ROOT / "data" / "processed" / "store_gwangju.csv"
    if not store_path.exists():
        raise FileNotFoundError("Run preprocess before features")
    stores = pd.read_csv(store_path, dtype={"bjd_code": str, "sigungu_code": str})
    stores["lat"] = pd.to_numeric(stores["lat"], errors="coerce")
    stores["lon"] = pd.to_numeric(stores["lon"], errors="coerce")
    stores = stores.dropna(subset=["lat", "lon"])
    x, y = lonlat_to_xy(stores["lon"], stores["lat"])
    stores["grid_x"] = np.floor(x / grid_size).astype(int)
    stores["grid_y"] = np.floor(y / grid_size).astype(int)
    stores["cell_id"] = stores["grid_x"].astype(str) + "_" + stores["grid_y"].astype(str)
    base = (
        stores.groupby("cell_id")
        .agg(
            grid_x=("grid_x", "first"),
            grid_y=("grid_y", "first"),
            lon=("lon", "mean"),
            lat=("lat", "mean"),
            sigungu_code=("sigungu_code", mode_or_blank),
            sigungu_name=("sigungu_name", mode_or_blank),
            dong_name=("dong_name", mode_or_blank),
            bjd_code=("bjd_code", mode_or_blank),
            total_store_count=("store_id", "size"),
            target_industry_count=("is_cafe", "sum"),
            food_count=("is_food", "sum"),
            convenience_count=("is_convenience", "sum"),
            life_service_count=("is_life_service", "sum"),
        )
        .reset_index()
    )
    base["other_store_count"] = base["total_store_count"] - base["target_industry_count"]
    base["has_target_industry"] = (base["target_industry_count"] > 0).astype(int)
    density_cut = base.loc[base["target_industry_count"] > 0, "target_industry_count"].quantile(0.7)
    if pd.isna(density_cut):
        density_cut = 1
    base["target_industry_density_high"] = (base["target_industry_count"] >= density_cut).astype(int)

    counts = stores.groupby(["cell_id", "industry_l2_name"]).size().rename("n").reset_index()
    counts["p"] = counts["n"] / counts.groupby("cell_id")["n"].transform("sum")
    diversity = (
        counts.groupby("cell_id")
        .agg(
            industry_diversity_hhi=("p", lambda s: float(np.square(s).sum())),
            industry_diversity_entropy=("p", lambda s: float(-(s * np.log(s + 1e-12)).sum())),
            industry_l2_unique=("industry_l2_name", "nunique"),
        )
        .reset_index()
    )
    features = base.merge(diversity, on="cell_id", how="left")

    bus_path = PROJECT_ROOT / "data" / "processed" / "transport_bus_gwangju.csv"
    subway_path = PROJECT_ROOT / "data" / "processed" / "subway_gwangju.csv"
    bus = pd.read_csv(bus_path) if bus_path.exists() and bus_path.stat().st_size > 10 else pd.DataFrame()
    subway = pd.read_csv(subway_path) if subway_path.exists() and subway_path.stat().st_size > 10 else pd.DataFrame()
    features = add_accessibility_features(features, bus, "bus", [300, 500, 1000])
    features = add_accessibility_features(features, subway, "subway", [500, 1000])

    land_path = PROJECT_ROOT / "data" / "processed" / "land_price_dong_summary.csv"
    if land_path.exists() and land_path.stat().st_size > 10:
        land = pd.read_csv(land_path, dtype={"bjd_code": str, "sigungu_code": str})
        features = features.merge(
            land[["bjd_code", "avg_land_price_dong", "median_land_price_dong", "land_price_count"]],
            on="bjd_code",
            how="left",
        )
        district_land = (
            land.groupby("sigungu_code")
            .agg(
                district_avg_land_price=("avg_land_price_dong", "mean"),
                district_median_land_price=("median_land_price_dong", "median"),
            )
            .reset_index()
        )
        features = features.merge(district_land, on="sigungu_code", how="left")
        features["avg_land_price_dong"] = features["avg_land_price_dong"].fillna(features["district_avg_land_price"])
        features["median_land_price_dong"] = features["median_land_price_dong"].fillna(features["district_median_land_price"])
    else:
        features["avg_land_price_dong"] = np.nan
        features["median_land_price_dong"] = np.nan
        features["land_price_count"] = 0

    real_path = PROJECT_ROOT / "data" / "processed" / "real_trade_dong_summary.csv"
    if real_path.exists() and real_path.stat().st_size > 10:
        real = pd.read_csv(real_path, dtype={"sigungu_code": str})
        real_dist = (
            real.groupby("sigungu_code")
            .agg(
                trade_price_median_sigungu=("trade_price_median_dong", "median"),
                trade_price_per_area_median_sigungu=("trade_price_per_area_median_dong", "median"),
                commercial_trade_count_sigungu=("commercial_trade_count_dong", "sum"),
            )
            .reset_index()
        )
        features = features.merge(real_dist, on="sigungu_code", how="left")
    else:
        features["trade_price_median_sigungu"] = np.nan
        features["trade_price_per_area_median_sigungu"] = np.nan
        features["commercial_trade_count_sigungu"] = 0

    building_path = PROJECT_ROOT / "data" / "processed" / "building_dong_summary.csv"
    if building_path.exists() and building_path.stat().st_size > 10:
        building = pd.read_csv(building_path, dtype={"bjd_code": str, "sigungu_code": str})
        features = features.merge(
            building[
                [
                    "bjd_code",
                    "building_age_avg_dong",
                    "gross_floor_area_avg_dong",
                    "commercial_building_ratio_dong",
                    "building_count_dong",
                ]
            ],
            on="bjd_code",
            how="left",
        )
    else:
        features["building_age_avg_dong"] = np.nan
        features["gross_floor_area_avg_dong"] = np.nan
        features["commercial_building_ratio_dong"] = np.nan
        features["building_count_dong"] = 0

    # Score components: all scores are descriptive proxy scores, not success predictions.
    features["demand_score"] = (
        0.45 * minmax_scale_safe(features["total_store_count"])
        + 0.25 * minmax_scale_safe(features["industry_diversity_entropy"])
        + 0.15 * minmax_scale_safe(features["bus_count_500m"])
        + 0.15 * minmax_scale_safe(features["subway_count_1000m"])
    )
    competition_raw = minmax_scale_safe(features["target_industry_count"], invert=True)
    low_signal = (features["target_industry_count"].eq(0)) & (
        features["total_store_count"] < features["total_store_count"].median()
    )
    features["competition_score"] = competition_raw.where(~low_signal, competition_raw * 0.7)
    complement = features["food_count"] + features["convenience_count"] + features["life_service_count"]
    features["industry_fit_score"] = (
        0.55 * minmax_scale_safe(features["industry_diversity_entropy"])
        + 0.45 * minmax_scale_safe(complement)
    )
    nearest_bus_score = minmax_scale_safe(features["nearest_bus_m"], invert=True)
    nearest_subway_score = minmax_scale_safe(features["nearest_subway_m"], invert=True)
    features["accessibility_score"] = (
        0.35 * nearest_bus_score
        + 0.25 * minmax_scale_safe(features["bus_count_500m"])
        + 0.20 * nearest_subway_score
        + 0.20 * minmax_scale_safe(features["subway_count_1000m"])
    )
    cost_proxy = features["median_land_price_dong"].copy()
    if "trade_price_per_area_median_sigungu" in features:
        cost_proxy = cost_proxy.fillna(features["trade_price_per_area_median_sigungu"])
    features["cost_burden_proxy"] = cost_proxy
    features["cost_score"] = minmax_scale_safe(features["cost_burden_proxy"], invert=True)

    scoring = load_config().get("scoring", {})
    features["suitability_score"] = (
        float(scoring.get("demand_weight", 0.35)) * features["demand_score"]
        + float(scoring.get("competition_weight", 0.25)) * features["competition_score"]
        + float(scoring.get("industry_fit_weight", 0.20)) * features["industry_fit_score"]
        + float(scoring.get("accessibility_weight", 0.10)) * features["accessibility_score"]
        + float(scoring.get("cost_weight", 0.10)) * features["cost_score"]
    ).round(2)
    features["risk_level"] = pd.cut(
        features["suitability_score"],
        bins=[-1, 55, 75, 101],
        labels=["높음", "중간", "낮음"],
    ).astype(str)
    features["candidate_id"] = [f"GJ-{i:04d}" for i in range(1, len(features) + 1)]

    feature_path = PROJECT_ROOT / "data" / "analysis" / "feature_dataset.csv"
    model_path = PROJECT_ROOT / "data" / "analysis" / "modeling_dataset.csv"
    cand_path = PROJECT_ROOT / "data" / "analysis" / "candidates_scored.csv"
    features.to_csv(feature_path, index=False, encoding="utf-8-sig")
    features.to_csv(model_path, index=False, encoding="utf-8-sig")
    features.sort_values("suitability_score", ascending=False).to_csv(cand_path, index=False, encoding="utf-8-sig")
    logging.info("Feature dataset rows: %d", len(features))
    make_feature_figures(features, stores)
    return features


def make_feature_figures(features: pd.DataFrame, stores: pd.DataFrame) -> None:
    fig_dir = PROJECT_ROOT / "outputs" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    district = stores.groupby("sigungu_name").size().sort_values(ascending=False)
    plt.figure(figsize=(8, 4.5))
    district.plot(kind="bar", color="#3478f6")
    plt.title("Store Counts by District")
    plt.ylabel("Stores")
    plt.tight_layout()
    plt.savefig(fig_dir / "district_store_counts.png", dpi=160)
    plt.close()

    ind = stores["industry_l2_name"].fillna("unknown").value_counts().head(12).sort_values()
    plt.figure(figsize=(8, 5))
    ind.plot(kind="barh", color="#0f9d78")
    plt.title("Top Industry Groups")
    plt.tight_layout()
    plt.savefig(fig_dir / "industry_distribution.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 4.5))
    features["suitability_score"].hist(bins=24, color="#ef7d22")
    plt.title("Suitability Score Distribution")
    plt.xlabel("Score")
    plt.ylabel("Grid cells")
    plt.tight_layout()
    plt.savefig(fig_dir / "score_distribution.png", dpi=160)
    plt.close()


MODEL_FEATURES = [
    "other_store_count",
    "total_store_count",
    "food_count",
    "convenience_count",
    "life_service_count",
    "industry_diversity_hhi",
    "industry_diversity_entropy",
    "industry_l2_unique",
    "nearest_bus_m",
    "bus_count_300m",
    "bus_count_500m",
    "bus_count_1000m",
    "nearest_subway_m",
    "subway_count_500m",
    "subway_count_1000m",
    "avg_land_price_dong",
    "median_land_price_dong",
    "trade_price_median_sigungu",
    "trade_price_per_area_median_sigungu",
    "commercial_trade_count_sigungu",
    "building_age_avg_dong",
    "gross_floor_area_avg_dong",
    "commercial_building_ratio_dong",
]


def prepare_model_frame(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    available = [c for c in MODEL_FEATURES if c in features.columns]
    X = features[available].apply(pd.to_numeric, errors="coerce")
    X = X.dropna(axis=1, how="all")
    available = list(X.columns)
    y = features["has_target_industry"].astype(int)
    keep = y.notna()
    X, y = X[keep], y[keep]
    return X, y, available


def evaluate_model(name: str, model: Any, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, Any]:
    pred = model.predict(X_test)
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X_test)[:, 1]
    else:
        proba = pred
    try:
        auroc = roc_auc_score(y_test, proba)
    except Exception:
        auroc = np.nan
    tn, fp, fn, tp = confusion_matrix(y_test, pred, labels=[0, 1]).ravel()
    return {
        "model": name,
        "auroc": round(float(auroc), 4) if pd.notna(auroc) else np.nan,
        "f1": round(float(f1_score(y_test, pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y_test, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, pred, zero_division=0)), 4),
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def train_validate_models() -> pd.DataFrame:
    logging.info("Training validation models")
    feature_path = PROJECT_ROOT / "data" / "analysis" / "modeling_dataset.csv"
    if not feature_path.exists():
        raise FileNotFoundError("Run features before model")
    features = pd.read_csv(feature_path)
    X, y, available = prepare_model_frame(features)
    if y.nunique() < 2 or len(y) < 20:
        raise RuntimeError("Modeling target has fewer than two classes or too few rows")
    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=float(load_config().get("analysis", {}).get("test_size", 0.2)),
        random_state=int(load_config().get("analysis", {}).get("random_state", 42)),
        stratify=stratify,
    )
    preprocess = ColumnTransformer(
        transformers=[("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), available)],
        remainder="drop",
    )
    models: dict[str, Any] = {
        "Logistic Regression": Pipeline(
            [
                ("prep", preprocess),
                ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
            ]
        ),
        "Random Forest": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=300,
                        max_depth=8,
                        min_samples_leaf=3,
                        class_weight="balanced_subsample",
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }
    if XGBClassifier is not None:
        pos = max(int((y_train == 1).sum()), 1)
        neg = max(int((y_train == 0).sum()), 1)
        models["XGBoost"] = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    XGBClassifier(
                        n_estimators=240,
                        max_depth=4,
                        learning_rate=0.05,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        eval_metric="logloss",
                        random_state=42,
                        n_jobs=2,
                        scale_pos_weight=neg / pos,
                    ),
                ),
            ]
        )
    if lgb is not None:
        models["LightGBM"] = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", lgb.LGBMClassifier(n_estimators=220, random_state=42, class_weight="balanced")),
            ]
        )

    rows: list[dict[str, Any]] = []
    fitted: dict[str, Any] = {}
    for name, model in models.items():
        try:
            model.fit(X_train, y_train)
            rows.append(evaluate_model(name, model, X_test, y_test))
            fitted[name] = model
            logging.info("Model %s complete", name)
        except Exception as exc:
            logging.warning("Model %s failed: %s", name, exc)
            rows.append({"model": name, "error": str(exc)})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(PROJECT_ROOT / "outputs" / "tables" / "model_metrics.csv", index=False, encoding="utf-8-sig")

    best_name = None
    if "auroc" in metrics.columns and metrics["auroc"].notna().any():
        best_name = metrics.sort_values("auroc", ascending=False).iloc[0]["model"]
    elif fitted:
        best_name = next(iter(fitted))
    if best_name and best_name in fitted:
        joblib.dump({"model": fitted[best_name], "features": available}, PROJECT_ROOT / "outputs" / "tables" / "best_model.joblib")
        proba = fitted[best_name].predict_proba(X)[:, 1]
        features["model_probability"] = proba
        features.to_csv(PROJECT_ROOT / "data" / "analysis" / "candidates_scored.csv", index=False, encoding="utf-8-sig")
        make_model_outputs(fitted[best_name], best_name, X_train, X_test, y_test, available, metrics)
    return metrics


def extract_feature_importance(model: Any, feature_names: list[str]) -> pd.DataFrame:
    estimator = model
    if isinstance(model, Pipeline):
        estimator = model.named_steps.get("model", model.steps[-1][1])
    importances = None
    if hasattr(estimator, "feature_importances_"):
        importances = estimator.feature_importances_
    elif hasattr(estimator, "coef_"):
        importances = np.abs(estimator.coef_[0])
    if importances is None or len(importances) != len(feature_names):
        importances = np.zeros(len(feature_names))
    out = pd.DataFrame({"feature": feature_names, "importance": importances})
    out["importance"] = pd.to_numeric(out["importance"], errors="coerce").fillna(0)
    return out.sort_values("importance", ascending=False)


def make_model_outputs(
    model: Any,
    best_name: str,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    feature_names: list[str],
    metrics: pd.DataFrame,
) -> None:
    fig_dir = PROJECT_ROOT / "outputs" / "figures"
    table_dir = PROJECT_ROOT / "outputs" / "tables"
    importance = extract_feature_importance(model, feature_names)
    importance.to_csv(table_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")

    top = importance.head(12).sort_values("importance")
    plt.figure(figsize=(8, 5))
    plt.barh(top["feature"], top["importance"], color="#5b6ee1")
    plt.title(f"Feature Importance ({best_name})")
    plt.tight_layout()
    plt.savefig(fig_dir / "feature_importance.png", dpi=160)
    plt.close()

    if "auroc" in metrics.columns:
        plot_metrics = metrics.dropna(subset=["auroc"], how="all").copy()
        if not plot_metrics.empty:
            plt.figure(figsize=(8, 4.5))
            x = np.arange(len(plot_metrics))
            plt.bar(x - 0.2, plot_metrics["auroc"], width=0.4, label="AUROC", color="#3478f6")
            plt.bar(x + 0.2, plot_metrics["f1"], width=0.4, label="F1", color="#ef7d22")
            plt.xticks(x, plot_metrics["model"], rotation=15, ha="right")
            plt.ylim(0, 1)
            plt.title("Model Metrics")
            plt.legend()
            plt.tight_layout()
            plt.savefig(fig_dir / "model_metrics.png", dpi=160)
            plt.close()

    if shap is not None:
        try:
            # SHAP on the tree estimator when possible. Logistic pipeline can skip to importance fallback.
            estimator = model.named_steps.get("model") if isinstance(model, Pipeline) else model
            if hasattr(estimator, "feature_importances_"):
                imputer = model.named_steps.get("imputer") if isinstance(model, Pipeline) else SimpleImputer(strategy="median").fit(X_train)
                X_sample = pd.DataFrame(imputer.transform(X_train.sample(min(500, len(X_train)), random_state=42)), columns=feature_names)
                explainer = shap.TreeExplainer(estimator)
                shap_values = explainer.shap_values(X_sample)
                vals = shap_values[1] if isinstance(shap_values, list) and len(shap_values) > 1 else shap_values
                shap.summary_plot(vals, X_sample, show=False, max_display=12)
                plt.tight_layout()
                plt.savefig(fig_dir / "shap_summary.png", dpi=160, bbox_inches="tight")
                plt.close()
        except Exception as exc:
            logging.warning("SHAP failed, using feature importance fallback: %s", exc)
            if not (fig_dir / "shap_summary.png").exists():
                plt.figure(figsize=(8, 5))
                plt.barh(top["feature"], top["importance"], color="#5b6ee1")
                plt.title("SHAP fallback: feature importance")
                plt.tight_layout()
                plt.savefig(fig_dir / "shap_summary.png", dpi=160)
                plt.close()
    elif not (fig_dir / "shap_summary.png").exists():
        plt.figure(figsize=(8, 5))
        plt.barh(top["feature"], top["importance"], color="#5b6ee1")
        plt.title("Feature importance fallback")
        plt.tight_layout()
        plt.savefig(fig_dir / "shap_summary.png", dpi=160)
        plt.close()


def reason_text(row: pd.Series) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    if row.get("accessibility_score", 0) >= 65:
        positive.append("대중교통 접근성이 상대적으로 좋아 접근성 점수에 긍정적으로 작용했습니다.")
    elif row.get("nearest_bus_m", 9999) > 600:
        negative.append("가까운 버스정류장까지의 거리가 길어 접근성 측면에서 주의가 필요합니다.")
    if row.get("demand_score", 0) >= 65:
        positive.append("반경 격자 내 전체 상가와 생활밀착 업종이 많아 수요 가능성 proxy가 높게 평가되었습니다.")
    else:
        negative.append("상가 밀도와 업종 다양성 proxy가 낮아 배후 수요 신호가 약할 수 있습니다.")
    if row.get("competition_score", 0) < 45:
        negative.append("동일 업종 밀집도가 높아 신규 진입 경쟁 위험이 있습니다.")
    else:
        positive.append("동일 업종 경쟁 강도가 과도하지 않아 경쟁 점수에 긍정적으로 반영되었습니다.")
    if row.get("cost_score", 0) < 45:
        negative.append("공시지가 기반 비용 부담 proxy가 높은 편입니다.")
    else:
        positive.append("공시지가 기반 비용 부담 proxy가 상대적으로 낮게 나타났습니다.")
    return positive[:3], negative[:3]


def export_web_data() -> None:
    logging.info("Exporting web JSON")
    cand_path = PROJECT_ROOT / "data" / "analysis" / "candidates_scored.csv"
    if not cand_path.exists():
        raise FileNotFoundError("Run model/features before web export")
    candidates = pd.read_csv(cand_path, dtype={"bjd_code": str, "sigungu_code": str})
    if "model_probability" not in candidates.columns:
        candidates["model_probability"] = np.nan
    candidates = candidates.sort_values("suitability_score", ascending=False).reset_index(drop=True)
    top_n = int(load_config().get("analysis", {}).get("top_candidate_count", 50))
    top = candidates.head(top_n).copy()
    exported = []
    for _, row in top.iterrows():
        pos, neg = reason_text(row)
        exported.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "name": f"{row.get('sigungu_name', '')} {row.get('dong_name', '')} 후보지",
                "sigungu_name": row.get("sigungu_name", ""),
                "dong_name": row.get("dong_name", ""),
                "lat": round(float(row.get("lat", 0)), 6),
                "lon": round(float(row.get("lon", 0)), 6),
                "industry": "카페",
                "suitability_score": round(float(row.get("suitability_score", 0)), 2),
                "risk_level": row.get("risk_level", "중간"),
                "demand_score": round(float(row.get("demand_score", 0)), 1),
                "competition_score": round(float(row.get("competition_score", 0)), 1),
                "accessibility_score": round(float(row.get("accessibility_score", 0)), 1),
                "cost_score": round(float(row.get("cost_score", 0)), 1),
                "industry_fit_score": round(float(row.get("industry_fit_score", 0)), 1),
                "model_probability": None if pd.isna(row.get("model_probability")) else round(float(row.get("model_probability")), 4),
                "positive_reasons": pos,
                "negative_reasons": neg,
            }
        )
    write_json(PROJECT_ROOT / "web" / "data" / "candidates.json", exported)
    top.to_csv(PROJECT_ROOT / "outputs" / "tables" / "top_candidates.csv", index=False, encoding="utf-8-sig")

    metrics_path = PROJECT_ROOT / "outputs" / "tables" / "model_metrics.csv"
    metrics = pd.read_csv(metrics_path) if metrics_path.exists() and metrics_path.stat().st_size > 10 else pd.DataFrame()
    metric_json = {
        "target_type": "proxy_location_suitability",
        "models": metrics.fillna("").to_dict("records"),
        "validation_note": "실제 생존 라벨이 없기 때문에 현재 업종 입지 패턴을 설명하는 proxy 모델 검증 결과입니다.",
    }
    write_json(PROJECT_ROOT / "web" / "data" / "model_metrics.json", metric_json)

    district = (
        candidates.groupby("sigungu_name", dropna=False)
        .agg(
            candidate_count=("candidate_id", "size"),
            store_count=("total_store_count", "sum"),
            cafe_count=("target_industry_count", "sum"),
            avg_land_price=("median_land_price_dong", "mean"),
            bus_stop_count=("bus_count_500m", "sum"),
            subway_station_count=("subway_count_1000m", "sum"),
            avg_suitability_score=("suitability_score", "mean"),
        )
        .reset_index()
    )
    district.to_csv(PROJECT_ROOT / "outputs" / "tables" / "district_summary.csv", index=False, encoding="utf-8-sig")
    write_json(PROJECT_ROOT / "web" / "data" / "district_summary.json", district.round(3).to_dict("records"))

    fi_path = PROJECT_ROOT / "outputs" / "tables" / "feature_importance.csv"
    fi = pd.read_csv(fi_path) if fi_path.exists() and fi_path.stat().st_size > 10 else pd.DataFrame(columns=["feature", "importance"])
    write_json(PROJECT_ROOT / "web" / "data" / "feature_importance.json", fi.head(20).round(6).to_dict("records"))

    score = candidates["suitability_score"]
    target = candidates["target_industry_count"]
    try:
        corr, pval = spearmanr(score, target, nan_policy="omit")
    except Exception:
        corr, pval = np.nan, np.nan
    high = candidates[candidates["suitability_score"] >= candidates["suitability_score"].quantile(0.8)]["target_industry_count"].mean()
    low = candidates[candidates["suitability_score"] <= candidates["suitability_score"].quantile(0.2)]["target_industry_count"].mean()
    validation = {
        "spearman_score_vs_target_count": None if pd.isna(corr) else round(float(corr), 4),
        "spearman_p_value": None if pd.isna(pval) else round(float(pval), 6),
        "top_20pct_avg_target_count": None if pd.isna(high) else round(float(high), 3),
        "bottom_20pct_avg_target_count": None if pd.isna(low) else round(float(low), 3),
        "note": "점수와 현재 카페 입지 패턴의 proxy 관계입니다. 창업 성공 또는 매출을 뜻하지 않습니다.",
    }
    write_json(PROJECT_ROOT / "web" / "data" / "validation_summary.json", validation)
    make_web_files()
    logging.info("Web export complete")


def make_web_files() -> None:
    (PROJECT_ROOT / "web" / "index.html").write_text(
        """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BizSpot AI</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <aside class="sidebar">
    <div class="brand">BizSpot AI</div>
    <nav>
      <button class="active">대시보드</button>
      <button>입지 분석</button>
      <button>업종 비교</button>
      <button>모델 검증</button>
      <button>인사이트</button>
      <button>설정</button>
    </nav>
  </aside>
  <main>
    <header class="topbar">
      <input id="search" placeholder="후보지 검색">
      <select><option>광주광역시</option></select>
      <select id="industry"><option>카페</option></select>
      <select id="radius"><option>500m</option><option>300m</option><option>1km</option></select>
      <select id="model"><option>Rule Score</option><option>XGBoost</option><option>RandomForest</option></select>
    </header>
    <section class="notice">
      <span>이 점수는 창업 성공을 보장하지 않습니다. 공공데이터 기반으로 후보지를 비교하기 위한 1차 필터링 지표입니다.</span>
      <span>유동인구 데이터가 없어 수요 가능성은 상가 밀도, 교통 접근성, 공시지가, 건물 특성 등의 proxy로 계산했습니다.</span>
      <span>비용 부담은 실제 월세가 아니라 공시지가와 상업용 거래 수준을 활용한 proxy입니다.</span>
    </section>
    <section class="layout">
      <div class="map-panel">
        <div class="map-head">
          <h1>광주 카페 입지 적합도</h1>
          <p>수요, 경쟁, 비용, 접근성, 업종 궁합의 균형 점수</p>
        </div>
        <div id="map" class="map"></div>
      </div>
      <aside class="detail" id="detail"></aside>
    </section>
    <section class="bottom">
      <div class="panel"><h2>상위 후보지 TOP 5</h2><div id="topList"></div></div>
      <div class="panel"><h2>모델 성능</h2><div id="metrics"></div></div>
      <div class="panel"><h2>자치구 요약</h2><div id="districts"></div></div>
      <div class="panel"><h2>판단 근거</h2><div id="importance"></div></div>
    </section>
  </main>
  <script src="app.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )
    (PROJECT_ROOT / "web" / "styles.css").write_text(
        """*{box-sizing:border-box}body{margin:0;font-family:Arial,'Noto Sans KR',sans-serif;background:#f4f6f8;color:#1e293b;display:flex;min-height:100vh}.sidebar{width:220px;background:#162033;color:white;padding:22px 16px;position:sticky;top:0;height:100vh}.brand{font-weight:800;font-size:22px;margin-bottom:24px}nav{display:grid;gap:8px}button,select,input{font:inherit}nav button{border:0;background:transparent;color:#cbd5e1;text-align:left;padding:10px 12px;border-radius:6px;cursor:pointer}nav button.active,nav button:hover{background:#24324d;color:white}main{flex:1;padding:18px;min-width:0}.topbar{display:grid;grid-template-columns:minmax(180px,1fr) 150px 120px 100px 160px;gap:10px;margin-bottom:12px}.topbar input,.topbar select{height:38px;border:1px solid #d5dde8;border-radius:6px;padding:0 10px;background:white}.notice{display:grid;gap:6px;font-size:13px;color:#475569;margin-bottom:14px}.notice span{background:#fff;border-left:3px solid #3478f6;padding:9px 10px;border-radius:4px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:14px}.map-panel,.detail,.panel{background:white;border:1px solid #dbe3ee;border-radius:8px}.map-head{padding:18px 18px 0}.map-head h1{margin:0;font-size:25px}.map-head p{margin:6px 0 0;color:#64748b}.map{position:relative;height:520px;margin:16px;border:1px solid #e2e8f0;background:linear-gradient(180deg,#f8fafc,#edf2f7);overflow:hidden;border-radius:6px}.marker{position:absolute;width:18px;height:18px;border-radius:50%;border:2px solid white;box-shadow:0 2px 8px #0003;transform:translate(-50%,-50%);cursor:pointer}.detail{padding:18px}.score{font-size:46px;font-weight:800;margin:4px 0 12px}.chips{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.chip{background:#edf2f7;border-radius:999px;padding:5px 9px;font-size:12px}.meter{margin:10px 0}.meter label{display:flex;justify-content:space-between;font-size:13px}.bar{height:8px;background:#e2e8f0;border-radius:99px;overflow:hidden}.bar span{display:block;height:100%;background:#3478f6}.bottom{display:grid;grid-template-columns:1.1fr 1fr 1fr 1fr;gap:14px;margin-top:14px}.panel{padding:16px;min-height:220px}.panel h2{font-size:16px;margin:0 0 12px}.row{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #eef2f7;padding:7px 0;font-size:13px}.muted{color:#64748b}.good{color:#0f9d78}.warn{color:#b45309}.bad{color:#c2410c}@media(max-width:1100px){.sidebar{display:none}.layout,.bottom{grid-template-columns:1fr}.topbar{grid-template-columns:1fr 1fr}.map{height:420px}}""",
        encoding="utf-8",
    )
    (PROJECT_ROOT / "web" / "app.js").write_text(
        """const $=s=>document.querySelector(s);const fmt=n=>Number.isFinite(+n)?(+n).toFixed(1):'-';Promise.all([fetch('data/candidates.json').then(r=>r.json()),fetch('data/model_metrics.json').then(r=>r.json()),fetch('data/district_summary.json').then(r=>r.json()),fetch('data/feature_importance.json').then(r=>r.json())]).then(([candidates,metrics,districts,importance])=>{let current=candidates[0];const lons=candidates.map(d=>d.lon),lats=candidates.map(d=>d.lat);const minLon=Math.min(...lons),maxLon=Math.max(...lons),minLat=Math.min(...lats),maxLat=Math.max(...lats);function color(s){return s>=75?'#0f9d78':s>=55?'#ef7d22':'#c2410c'}function renderMap(list){const map=$('#map');map.innerHTML='';list.forEach(d=>{const x=(d.lon-minLon)/(maxLon-minLon||1)*88+6;const y=94-((d.lat-minLat)/(maxLat-minLat||1)*88+6);const m=document.createElement('button');m.className='marker';m.style.left=x+'%';m.style.top=y+'%';m.style.background=color(d.suitability_score);m.title=d.name+' '+d.suitability_score;m.onclick=()=>{current=d;renderDetail()};map.appendChild(m)})}function meter(label,val){return `<div class="meter"><label><span>${label}</span><b>${fmt(val)}</b></label><div class="bar"><span style="width:${Math.max(0,Math.min(100,val||0))}%"></span></div></div>`}function renderDetail(){const d=current;$('#detail').innerHTML=`<div class="muted">${d.candidate_id}</div><h2>${d.name}</h2><div class="score">${fmt(d.suitability_score)}</div><div class="chips"><span class="chip">${d.industry}</span><span class="chip">위험도 ${d.risk_level}</span><span class="chip">모델확률 ${d.model_probability??'-'}</span></div>${meter('수요 가능성',d.demand_score)}${meter('경쟁 강도 역산',d.competition_score)}${meter('접근성',d.accessibility_score)}${meter('비용 부담 역산',d.cost_score)}${meter('업종 궁합',d.industry_fit_score)}<h3>추천 사유</h3><ul>${d.positive_reasons.map(x=>`<li>${x}</li>`).join('')}</ul><h3>주의 사유</h3><ul>${d.negative_reasons.map(x=>`<li>${x}</li>`).join('')}</ul>`}function renderLists(){document.querySelector('#topList').innerHTML=candidates.slice(0,5).map(d=>`<div class="row"><span>${d.name}</span><b>${fmt(d.suitability_score)}</b></div>`).join('');document.querySelector('#metrics').innerHTML=(metrics.models||[]).map(d=>`<div class="row"><span>${d.model}</span><span>AUROC ${d.auroc||'-'} / F1 ${d.f1||'-'}</span></div>`).join('');document.querySelector('#districts').innerHTML=districts.map(d=>`<div class="row"><span>${d.sigungu_name}</span><span>${fmt(d.avg_suitability_score)}</span></div>`).join('');document.querySelector('#importance').innerHTML=importance.slice(0,8).map(d=>`<div class="row"><span>${d.feature}</span><span>${fmt(d.importance)}</span></div>`).join('')}$('#search').addEventListener('input',e=>{const q=e.target.value.trim();const list=q?candidates.filter(d=>d.name.includes(q)||d.sigungu_name.includes(q)||d.dong_name.includes(q)):candidates;renderMap(list)});renderMap(candidates);renderDetail();renderLists()});""",
        encoding="utf-8",
    )


def generate_reports() -> None:
    logging.info("Generating reports")
    processed = PROJECT_ROOT / "data" / "processed"
    analysis = PROJECT_ROOT / "data" / "analysis"
    reports = PROJECT_ROOT / "outputs" / "reports"
    tables = PROJECT_ROOT / "outputs" / "tables"
    store = pd.read_csv(processed / "store_gwangju.csv") if (processed / "store_gwangju.csv").exists() else pd.DataFrame()
    features = pd.read_csv(analysis / "candidates_scored.csv") if (analysis / "candidates_scored.csv").exists() else pd.DataFrame()
    metrics = pd.read_csv(tables / "model_metrics.csv") if (tables / "model_metrics.csv").exists() else pd.DataFrame()
    store_quality_path = tables / "store_quality.json"
    store_quality = json.loads(store_quality_path.read_text(encoding="utf-8")) if store_quality_path.exists() else {}
    transport_quality_path = tables / "transport_quality.json"
    transport_quality = json.loads(transport_quality_path.read_text(encoding="utf-8")) if transport_quality_path.exists() else {}

    data_quality = [
        "# 데이터 정합성 확인 보고서",
        "",
        "## 핵심 요약",
        f"- 광주 상가 최종 사용 행 수: {len(store):,}",
        f"- 좌표 결측 제거 행 수: {store_quality.get('missing_coord_rows', 0):,}",
        f"- 광주 bounding box 밖 제거 행 수: {store_quality.get('outside_bbox_rows', 0):,}",
        f"- 최종 후보 격자 수: {len(features):,}",
        f"- 광주 버스정류장 좌표 행 수: {transport_quality.get('final_bus_rows', 0):,}",
        f"- 광주 자체 정류소 좌표 여부: {transport_quality.get('local_bus_has_coordinates', False)}",
        "",
        "## 좌표 정합성",
        "",
        "| 항목 | 값 |",
        "|---|---:|",
        f"| 전체 광주 상가 후보 행 | {store_quality.get('gwangju_rows_before_coord_filter', 0):,} |",
        f"| 위도/경도 결측 행 | {store_quality.get('missing_coord_rows', 0):,} |",
        f"| 광주 bounding box 밖 행 | {store_quality.get('outside_bbox_rows', 0):,} |",
        f"| 중복 상가업소번호 행 | {store_quality.get('duplicate_store_id_rows', 0):,} |",
        f"| 최종 사용 행 | {store_quality.get('final_rows', len(store)):,} |",
        "",
        "## 주의사항",
        "- 광주 정류소 로컬 파일은 좌표가 없어 전국 버스정류장 위치정보를 좌표 fallback으로 사용했다.",
        "- D8 유동인구 데이터는 없으므로 실패 처리하지 않고 proxy 변수로 대체했다.",
        "- 공시지가와 실거래가는 임대료가 아니라 비용 부담 proxy로만 해석한다.",
    ]
    (reports / "data_quality_report.md").write_text("\n".join(data_quality), encoding="utf-8")

    best_line = "모델 결과 없음"
    if not metrics.empty and "auroc" in metrics.columns and metrics["auroc"].notna().any():
        best = metrics.sort_values("auroc", ascending=False).iloc[0]
        best_line = f"{best['model']}가 AUROC {best['auroc']}로 가장 높게 나타났다."
    model_report = [
        "# 모델 검증 보고서",
        "",
        "## 검증 문제",
        "단일 시점 상가 데이터이므로 생존/폐업 예측이 아니라 카페 업종의 현재 입지 패턴을 설명하는 proxy 모델로 검증했다.",
        "",
        "## 모델 성능",
        best_line,
        "",
        dataframe_to_markdown(metrics) if not metrics.empty else "모델 지표가 생성되지 않았다.",
        "",
        "## 해석",
        "- 성능이 높더라도 이는 창업 성공, 매출, 폐업 방지를 예측했다는 뜻이 아니다.",
        "- 공공데이터 기반 변수들이 현재 업종 입지 패턴을 어느 정도 설명하는지 확인한 결과다.",
        "- SHAP 또는 feature importance는 모델 판단 근거이며 인과관계 증명이 아니다.",
    ]
    (reports / "model_validation_report.md").write_text("\n".join(model_report), encoding="utf-8")

    validation_path = PROJECT_ROOT / "web" / "data" / "validation_summary.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
    top_score = features["suitability_score"].max() if not features.empty else np.nan
    summary = [
        "# BizSpot AI 실험 요약",
        "",
        "## 1. 연구 의도 해석",
        "BizSpot AI는 유명 상권을 찾는 시스템이 아니라 창업자가 감당해야 하는 수요, 경쟁, 비용, 접근성, 업종 궁합의 균형을 비교하는 시스템이다.",
        "",
        "## 2. 핵심 문제의식",
        "좋은 상권이라고 해서 신규 창업자에게 항상 좋은 입지는 아니다. 동일 업종 경쟁과 비용 부담이 높으면 위험이 커질 수 있다.",
        "",
        "## 3. 핵심 가설",
        "상가 밀도, 업종 다양성, 대중교통 접근성, 공시지가 같은 공공데이터 proxy는 카페 입지 패턴의 일부를 설명할 수 있다.",
        "",
        "## 4. 사용 데이터",
        "상가정보, 업종코드, 법정동코드, 개별공시지가, 버스정류장, 도시철도역, 선택적 건축물대장/실거래가 API를 사용했다.",
        "",
        "## 5. 데이터 정합성 확인",
        f"광주 상가 {len(store):,}개와 후보 격자 {len(features):,}개를 생성했다. 좌표 결측과 광주 외부 좌표는 제거했다.",
        "",
        "## 6. 실험 설계",
        "실제 생존 라벨이 없기 때문에 B안 격자 기반 proxy 검증으로 진행했다. target은 격자 내 카페 존재 여부다.",
        "",
        "## 7. 피처 생성",
        "전체 상가 수, 타 업종 수, 업종 다양성, 교통 접근성, 공시지가, 선택적 건물/실거래가 변수를 만들었다.",
        "",
        "## 8. 모델 검증",
        best_line,
        "",
        "## 9. 결과 해석",
        f"점수와 카페 수의 Spearman 상관계수는 {validation.get('spearman_score_vs_target_count', 'NA')}로 관찰되었다. 이 값은 점수 산식이 현재 입지 패턴과 어떤 관계를 보이는지 확인하는 보조 지표다.",
        "",
        "## 10. 웹 구현 방향",
        "정적 HTML/CSS/JS 대시보드에서 후보지 TOP 50, 세부 점수, 모델 성능, 자치구 요약, feature importance를 확인할 수 있게 했다.",
        "",
        "## 11. 한계",
        "유동인구, 매출, 임대료, 폐업 이력 데이터가 없으므로 창업 성공 예측이라고 볼 수 없다. 실거래가와 공시지가는 비용 부담 proxy다.",
        "",
        "유동인구 데이터가 확보되지 않았기 때문에 본 프로젝트는 실제 유동인구를 직접 사용하지 않고, 전체 상가 밀도·대중교통 접근성·공시지가·건물 용도 등을 수요 가능성의 대리변수로 사용한다.",
        "",
        "## 12. 다음 실험",
        "유동인구, 매출 추정, 임대료, 폐업 이력 또는 다중 시점 상가정보가 확보되면 생존 라벨 기반 검증으로 확장할 수 있다.",
        "",
        "## 13. 발표용 인사이트",
        "Insight 1. 좋은 상권과 창업하기 좋은 상권은 다를 수 있다.",
        "Insight 2. 경쟁 밀집도는 수요 신호이면서 동시에 위험 요인이다.",
        "Insight 3. 비용 부담은 입지 판단에서 반드시 함께 봐야 한다.",
        "Insight 4. D8 유동인구 데이터가 없어도 1차 후보지 필터링은 가능하다.",
        "",
        "## 14. 결론",
        "본 프로젝트의 핵심 결론은 좋은 상권과 창업하기 좋은 상권은 다를 수 있다는 점이다. 유동성과 접근성이 높더라도 동일 업종 경쟁이 과도하고 비용 부담이 크면 신규 창업자에게는 위험할 수 있다. 따라서 창업 입지는 수요, 경쟁, 비용, 접근성, 업종 궁합의 균형으로 판단해야 한다.",
        "",
        f"이번 실험에서 계산된 최고 후보지 점수는 {top_score:.2f}점이다." if pd.notna(top_score) else "",
    ]
    (reports / "experiment_summary.md").write_text("\n".join(summary), encoding="utf-8")
    make_readme()


def make_readme() -> None:
    readme = [
        "# BizSpot AI",
        "",
        "BizSpot AI는 모델 검증을 먼저 수행하고, 그 결과를 지도형 웹서비스로 보여주는 광주 소상공인 창업 입지 분석 시스템입니다. 좋은 상권이 곧 창업하기 좋은 상권은 아니라는 문제의식에서 출발해, 수요·경쟁·비용·접근성·업종 궁합의 균형을 데이터로 확인합니다.",
        "",
        "## 데이터 목록",
        "- D0 법정동코드",
        "- D1 소상공인시장진흥공단 상가정보",
        "- D2 상가정보 업종코드",
        "- D3 국토교통부 건축HUB 건축물대장정보 서비스",
        "- D4 국토교통부 상업업무용 부동산 매매 실거래가 자료",
        "- D5 개별공시지가",
        "- D6 버스정류장",
        "- D7 광주 도시철도",
        "- D8 유동인구: 미확보, proxy 대체",
        "",
        "## 설치 방법",
        "```bash",
        "python -m pip install -r requirements.txt",
        "```",
        "",
        "## .env 설정 방법",
        "`.env.example`을 참고해 로컬에 `.env`를 만들고 `DATA_GO_KR_SERVICE_KEY`를 설정한다. API 키는 코드나 Git에 넣지 않는다.",
        "",
        "## 실행 방법",
        "```bash",
        "python scripts/run_all.py --mode scan",
        "python scripts/run_all.py --mode preprocess",
        "python scripts/run_all.py --mode features",
        "python scripts/run_all.py --mode model",
        "python scripts/run_all.py --mode web",
        "python scripts/run_all.py --mode report",
        "python scripts/run_all.py --mode all",
        "```",
        "",
        "## 산출물 위치",
        "- 전처리: `data/processed/`",
        "- 분석 데이터: `data/analysis/`",
        "- 표/그림/보고서: `outputs/`",
        "- 웹 대시보드: `web/index.html`",
        "",
        "## 모델 검증 방식",
        "단일 시점 데이터이므로 창업 성공이나 생존 예측이 아니라 현재 카페 입지 패턴을 설명하는 proxy 모델로 검증한다.",
        "",
        "## 웹 실행 방법",
        "정적 파일이므로 `web/index.html`을 브라우저에서 열면 된다. 일부 브라우저의 로컬 JSON 제한이 있으면 `python -m http.server 8000 -d web`으로 실행한다.",
        "",
        "## 한계와 주의사항",
        "- 이 점수는 창업 성공을 보장하지 않는다.",
        "- 유동인구 데이터가 없어 수요 가능성은 proxy로 계산했다.",
        "- 비용 부담은 실제 월세가 아니라 공시지가와 상업용 거래 수준 기반 proxy다.",
        "- SHAP/feature importance는 모델 판단 근거이지 인과관계 증명이 아니다.",
        "",
        "## 주요 출처",
        "- 행정안전부 법정동코드: https://www.code.go.kr/stdcode/regCodeL.do",
        "- 상가정보 파일/API: https://www.data.go.kr/data/15083033/fileData.do, https://www.data.go.kr/data/15012005/openapi.do",
        "- 업종코드: https://www.data.go.kr/data/15067631/fileData.do",
        "- 건축물대장정보: https://www.data.go.kr/data/15134735/openapi.do",
        "- 상업업무용 실거래가: https://www.data.go.kr/data/15126463/openapi.do",
        "- 버스정류장: https://www.data.go.kr/data/15067528/fileData.do",
        "- 광주 도시철도: https://www.data.go.kr/data/15109340/fileData.do",
    ]
    (PROJECT_ROOT / "README.md").write_text("\n".join(readme), encoding="utf-8")


def run_mode(mode: str) -> None:
    setup_logging()
    ensure_dirs()
    logging.info("Running mode: %s", mode)
    if mode == "scan":
        scan_data()
    elif mode == "preprocess":
        preprocess_all()
    elif mode == "features":
        build_features()
    elif mode == "model":
        train_validate_models()
    elif mode == "web":
        export_web_data()
    elif mode == "report":
        generate_reports()
    elif mode == "all":
        scan_data()
        preprocess_all()
        build_features()
        train_validate_models()
        export_web_data()
        generate_reports()
    else:
        raise ValueError(f"Unknown mode: {mode}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scan", "preprocess", "features", "model", "web", "report", "all"], default="all")
    args = parser.parse_args(argv)
    run_mode(args.mode)


if __name__ == "__main__":
    main()
