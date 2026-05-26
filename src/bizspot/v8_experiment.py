from __future__ import annotations

import argparse
import io
import json
import logging
import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import BallTree
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from bizspot.pipeline import (
    DOWNLOADS,
    GWANGJU_BOUNDS,
    GWANGJU_SIGUNGU_CODES,
    GWANGJU_SIGUNGU_NAMES,
    PROJECT_ROOT,
    clean_number,
    detect_csv_encoding_from_bytes,
    in_gwangju_bbox,
    lonlat_to_xy,
    minmax_scale_safe,
    write_json,
)

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - optional dependency
    XGBClassifier = None

try:
    import lightgbm as lgb
except Exception:  # pragma: no cover - optional dependency
    lgb = None


SNAPSHOT_DATES = [
    "20220630",
    "20221231",
    "20230630",
    "20231231",
    "20240630",
    "20241231",
    "20250630",
    "20251231",
]
SNAPSHOT_MONTHS = [d[:6] for d in SNAPSHOT_DATES]
GWANGJU_KEYWORD = "\uad11\uc8fc"
V8_ROOT = PROJECT_ROOT / "data" / "v8"
V8_PROCESSED = V8_ROOT / "processed"
V8_ANALYSIS = V8_ROOT / "analysis"
V8_OUTPUTS = PROJECT_ROOT / "outputs" / "v8"
V8_REPORTS = V8_OUTPUTS / "reports"
V8_TABLES = V8_OUTPUTS / "tables"
V8_WEB = V8_OUTPUTS / "web_ready_data"
RADIUS_M = [100, 300, 500, 1000]
FUZZY_MATCH_THRESHOLD = 85.0
FUZZY_REVIEW_THRESHOLD = 70.0
FUZZY_BLOCK_RADIUS_M = 300
MAX_MODEL_ROWS = 30_000
RANDOM_STATE = 42


@dataclass
class SnapshotEntry:
    snapshot_date: str
    zip_path: Path
    entry_name: str
    decoded_entry_name: str
    nested_zip_entry: str | None
    file_size: int
    encoding: str
    columns: list[str]
    row_count_estimate: int | None


def ensure_v8_dirs() -> None:
    for path in [V8_PROCESSED, V8_ANALYSIS, V8_REPORTS, V8_TABLES, V8_WEB]:
        path.mkdir(parents=True, exist_ok=True)


def setup_v8_logging() -> None:
    ensure_v8_dirs()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(V8_REPORTS / "v8_pipeline.log", encoding="utf-8"),
        ],
        force=True,
    )


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(map(str, cols)) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if pd.isna(val):
                vals.append("")
            elif isinstance(val, float):
                vals.append(f"{val:.4f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def safe_to_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def decode_zip_name(name: str) -> list[str]:
    variants = [name]
    for src in ["cp437", "cp850"]:
        for dst in ["cp949", "euc-kr", "utf-8"]:
            try:
                decoded = name.encode(src).decode(dst)
                if decoded not in variants:
                    variants.append(decoded)
            except Exception:
                continue
    return variants


def find_snapshot_zip(snapshot_date: str) -> Path:
    matches = [
        p
        for p in DOWNLOADS.glob("*.zip")
        if snapshot_date in p.name and p.stat().st_size > 250_000_000
    ]
    if not matches:
        raise FileNotFoundError(f"상가정보 스냅샷 ZIP을 찾지 못했습니다: {snapshot_date}")
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def open_snapshot_zip(zip_path: Path):
    zf = zipfile.ZipFile(zip_path)
    names = zf.namelist()
    nested_name = None
    nested_zip = None
    if len(names) <= 3 and any(n.lower().endswith(".zip") for n in names):
        nested_name = next(n for n in names if n.lower().endswith(".zip"))
        nested_zip = zipfile.ZipFile(io.BytesIO(zf.read(nested_name)))
        return zf, nested_zip, nested_name
    return zf, zf, nested_name


def find_gwangju_entry(zip_reader: zipfile.ZipFile) -> tuple[str, str]:
    for name in zip_reader.namelist():
        if not name.lower().endswith(".csv"):
            continue
        for decoded in decode_zip_name(name):
            if GWANGJU_KEYWORD in decoded and decoded.lower().endswith(".csv"):
                return name, decoded
    raise FileNotFoundError("ZIP 내부에서 광주 CSV를 찾지 못했습니다.")


def estimate_zip_entry_rows(zip_reader: zipfile.ZipFile, entry_name: str) -> int | None:
    try:
        with zip_reader.open(entry_name) as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return None


def read_snapshot_entry(entry: SnapshotEntry, nrows: int | None = None) -> pd.DataFrame:
    outer, reader, _ = open_snapshot_zip(entry.zip_path)
    try:
        with reader.open(entry.entry_name) as f:
            return pd.read_csv(f, encoding=entry.encoding, low_memory=False, nrows=nrows)
    finally:
        if reader is not outer:
            reader.close()
        outer.close()


def scan_snapshots() -> list[SnapshotEntry]:
    logging.info("Scanning v8 snapshot files")
    entries: list[SnapshotEntry] = []
    rows = []
    for snapshot_date in SNAPSHOT_DATES:
        zip_path = find_snapshot_zip(snapshot_date)
        outer, reader, nested_name = open_snapshot_zip(zip_path)
        try:
            entry_name, decoded_name = find_gwangju_entry(reader)
            info = reader.getinfo(entry_name)
            with reader.open(entry_name) as f:
                sample = f.read(256_000)
            encoding = detect_csv_encoding_from_bytes(sample)
            with reader.open(entry_name) as f:
                columns = list(pd.read_csv(f, encoding=encoding, nrows=2).columns)
            row_count = estimate_zip_entry_rows(reader, entry_name)
        finally:
            if reader is not outer:
                reader.close()
            outer.close()
        entry = SnapshotEntry(
            snapshot_date=snapshot_date,
            zip_path=zip_path,
            entry_name=entry_name,
            decoded_entry_name=decoded_name,
            nested_zip_entry=nested_name,
            file_size=info.file_size,
            encoding=encoding,
            columns=list(map(str, columns)),
            row_count_estimate=row_count,
        )
        entries.append(entry)
        rows.append(
            {
                "snapshot_date": snapshot_date,
                "zip_path": str(zip_path),
                "nested_zip_entry": nested_name or "",
                "gwangju_entry": decoded_name,
                "entry_size_bytes": info.file_size,
                "encoding": encoding,
                "column_count": len(columns),
                "row_count_estimate": row_count,
                "columns_first8": ", ".join(map(str, columns[:8])),
            }
        )
    scan_df = pd.DataFrame(rows)
    safe_to_csv(scan_df, V8_TABLES / "data_file_scan.csv")
    (V8_REPORTS / "data_file_scan.md").write_text(
        "# v8 데이터 파일 스캔\n\n"
        + dataframe_to_markdown(scan_df)
        + "\n\n모든 스냅샷에서 광주 CSV를 확인했다. 2022년 파일은 중첩 ZIP 구조이며, 일부 ZIP entry명은 cp437 기반 복원이 필요하다.\n",
        encoding="utf-8",
    )
    (V8_REPORTS / "data_mapping_report.md").write_text(
        "# v8 데이터 매핑 보고서\n\n"
        "반기별 상가정보 8개 파일은 모두 D1 상가정보 스냅샷으로 매핑한다. "
        "기존 법정동, 교통, 공시지가, 실거래가 전처리 결과는 v8 feature 생성의 보조 데이터로 사용한다.\n\n"
        + dataframe_to_markdown(
            scan_df[
                [
                    "snapshot_date",
                    "gwangju_entry",
                    "encoding",
                    "column_count",
                    "row_count_estimate",
                ]
            ]
        ),
        encoding="utf-8",
    )
    return entries


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).lower()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"주식회사|유한회사|\(주\)|㈜|본점|지점|직영점|가맹점", "", text)
    text = re.sub(r"[^0-9a-zA-Z가-힣]", "", text)
    return text.strip()


def normalize_address(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("광주 광역시", "광주광역시")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^0-9a-zA-Z가-힣\- ]", "", text)
    return text.strip().lower()


def normalize_code(value: Any, length: int) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    text = re.sub(r"\D", "", text)
    if not text:
        return ""
    return text.zfill(length)


def map_industry_group(row: pd.Series) -> str:
    text = " ".join(
        [
            str(row.get("industry_l1_name", "")),
            str(row.get("industry_l2_name", "")),
            str(row.get("industry_l3_name", "")),
            str(row.get("store_name", "")),
        ]
    )
    if re.search("커피|카페|다방|비알코올|음료", text):
        return "cafe"
    if re.search("제과|제빵|베이커리|디저트|도넛|케이크|빵", text):
        return "dessert_bakery"
    if re.search("분식|김밥|떡볶|라면", text):
        return "bunsik"
    if re.search("치킨|닭강정", text):
        return "chicken"
    if re.search("편의점", text):
        return "convenience_store"
    if re.search("미용|헤어|이발|네일", text):
        return "beauty_hair"
    if re.search("세탁|빨래방|크리닝", text):
        return "laundry"
    if re.search("음식|한식|중식|일식|서양식|식당|국밥|고기|구이|해장국|족발|보쌈|피자|버거", text):
        return "restaurant_general"
    return "other"


def standardize_snapshot(df: pd.DataFrame, snapshot_date: str) -> pd.DataFrame:
    rename = {
        "상가업소번호": "store_id",
        "상호명": "store_name",
        "지점명": "branch_name",
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
    df["snapshot_date"] = snapshot_date
    df["snapshot_ym"] = snapshot_date[:6]
    df["store_id"] = df["store_id"].astype(str)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["lat", "lon"])
    df = df[in_gwangju_bbox(df)]
    df["bjd_code"] = df["bjd_code"].map(lambda v: normalize_code(v, 10))
    df["sigungu_code"] = df["sigungu_code"].map(lambda v: normalize_code(v, 5)[-5:] if normalize_code(v, 5) else "")
    df.loc[df["sigungu_code"].eq(""), "sigungu_code"] = df.loc[df["sigungu_code"].eq(""), "bjd_code"].str[:5]
    df = df[df["sigungu_code"].isin(GWANGJU_SIGUNGU_CODES)].copy()
    df["sigungu_name"] = df["sigungu_code"].map(GWANGJU_SIGUNGU_NAMES).fillna(df["sigungu_name"])
    df["industry_group"] = df.apply(map_industry_group, axis=1)
    df["normalized_name"] = df["store_name"].map(normalize_text)
    addr = df["road_address"].where(df["road_address"].astype(str).str.strip().ne(""), df["jibun_address"])
    df["normalized_address"] = addr.map(normalize_address)
    df["x_m"], df["y_m"] = lonlat_to_xy(df["lon"], df["lat"])
    df["row_seq"] = np.arange(len(df))
    df["snapshot_uid"] = snapshot_date + "_" + df["store_id"].astype(str) + "_" + df["row_seq"].astype(str)
    keep = [
        "snapshot_uid",
        "snapshot_date",
        "snapshot_ym",
        "store_id",
        "store_name",
        "branch_name",
        "industry_l1_code",
        "industry_l1_name",
        "industry_l2_code",
        "industry_l2_name",
        "industry_l3_code",
        "industry_l3_name",
        "industry_group",
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
        "x_m",
        "y_m",
        "normalized_name",
        "normalized_address",
    ]
    out = df[keep].drop_duplicates(subset=["snapshot_uid"]).copy()
    logging.info(
        "Snapshot %s standardized: source=%d final=%d removed=%d",
        snapshot_date,
        before,
        len(out),
        before - len(out),
    )
    return out


def build_store_panel(entries: list[SnapshotEntry]) -> pd.DataFrame:
    logging.info("Building v8 store panel")
    frames = []
    quality_rows = []
    for entry in entries:
        raw = read_snapshot_entry(entry)
        standardized = standardize_snapshot(raw, entry.snapshot_date)
        safe_to_csv(standardized, V8_PROCESSED / f"store_snapshot_{entry.snapshot_date}_gwangju.csv")
        frames.append(standardized)
        quality_rows.append(
            {
                "snapshot_date": entry.snapshot_date,
                "encoding": entry.encoding,
                "source_rows_estimate": entry.row_count_estimate,
                "processed_rows": len(standardized),
                "missing_coord_rows_estimate": (entry.row_count_estimate or len(raw)) - len(standardized),
                "industry_group_unique": standardized["industry_group"].nunique(),
                "other_industry_ratio": round(float((standardized["industry_group"] == "other").mean()), 4),
            }
        )
    panel = pd.concat(frames, ignore_index=True)
    safe_to_csv(panel, V8_PROCESSED / "store_panel_gwangju.csv")
    quality_df = pd.DataFrame(quality_rows)
    safe_to_csv(quality_df, V8_TABLES / "snapshot_quality.csv")
    return panel


class UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {v: v for v in values}

    def find(self, x: str) -> str:
        parent = self.parent.setdefault(x, x)
        if parent != x:
            self.parent[x] = self.find(parent)
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def match_score(prev: pd.Series, nxt: pd.Series, distance_m: float) -> float:
    name_score = text_similarity(prev["normalized_name"], nxt["normalized_name"])
    address_score = text_similarity(prev["normalized_address"], nxt["normalized_address"])
    industry_score = 1.0 if prev["industry_group"] == nxt["industry_group"] else 0.0
    distance_score = max(0.0, 1.0 - distance_m / FUZZY_BLOCK_RADIUS_M)
    if distance_m <= 50:
        distance_score = 1.0
    return 40 * name_score + 25 * address_score + 20 * industry_score + 15 * distance_score


def direct_id_matches(prev: pd.DataFrame, nxt: pd.DataFrame) -> tuple[pd.DataFrame, set[str], set[str]]:
    next_by_id = nxt.drop_duplicates("store_id").set_index("store_id")
    rows = []
    matched_prev: set[str] = set()
    matched_next: set[str] = set()
    for _, row in prev.iterrows():
        store_id = row["store_id"]
        if store_id in next_by_id.index:
            next_row = next_by_id.loc[store_id]
            dist = math.hypot(float(row["x_m"]) - float(next_row["x_m"]), float(row["y_m"]) - float(next_row["y_m"]))
            rows.append(
                {
                    "from_snapshot": row["snapshot_date"],
                    "to_snapshot": next_row["snapshot_date"],
                    "from_uid": row["snapshot_uid"],
                    "to_uid": next_row["snapshot_uid"],
                    "from_store_id": store_id,
                    "to_store_id": store_id,
                    "match_method": "direct_id",
                    "match_confidence": 100.0,
                    "distance_m": round(dist, 2),
                    "review_flag": False,
                }
            )
            matched_prev.add(row["snapshot_uid"])
            matched_next.add(next_row["snapshot_uid"])
    return pd.DataFrame(rows), matched_prev, matched_next


def fuzzy_block_matches(prev: pd.DataFrame, nxt: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    candidate_rows = []
    stats = {
        "blocks_considered": 0,
        "candidate_pairs_after_blocking": 0,
        "review_pairs_70_84": 0,
        "accepted_pairs_85_plus": 0,
    }
    for (sigungu, industry), prev_block in prev.groupby(["sigungu_code", "industry_group"], dropna=False):
        nxt_block = nxt[(nxt["sigungu_code"] == sigungu) & (nxt["industry_group"] == industry)]
        if prev_block.empty or nxt_block.empty:
            continue
        stats["blocks_considered"] += 1
        next_xy = nxt_block[["x_m", "y_m"]].to_numpy(dtype=float)
        tree = BallTree(next_xy, metric="euclidean")
        prev_xy = prev_block[["x_m", "y_m"]].to_numpy(dtype=float)
        indices, distances = tree.query_radius(prev_xy, r=FUZZY_BLOCK_RADIUS_M, return_distance=True)
        nxt_records = nxt_block.reset_index(drop=True)
        prev_records = prev_block.reset_index(drop=True)
        for i, cand_idx in enumerate(indices):
            if len(cand_idx) == 0:
                continue
            order = np.argsort(distances[i])[:20]
            for pos in order:
                j = int(cand_idx[pos])
                distance = float(distances[i][pos])
                prev_row = prev_records.iloc[i]
                next_row = nxt_records.iloc[j]
                # Same 법정동 is preferred; nearby cross-dong candidates are allowed only because the 300m spatial block already holds.
                score = match_score(prev_row, next_row, distance)
                stats["candidate_pairs_after_blocking"] += 1
                if score >= FUZZY_REVIEW_THRESHOLD:
                    candidate_rows.append(
                        {
                            "from_snapshot": prev_row["snapshot_date"],
                            "to_snapshot": next_row["snapshot_date"],
                            "from_uid": prev_row["snapshot_uid"],
                            "to_uid": next_row["snapshot_uid"],
                            "from_store_id": prev_row["store_id"],
                            "to_store_id": next_row["store_id"],
                            "match_method": "blocked_fuzzy",
                            "match_confidence": round(score, 2),
                            "distance_m": round(distance, 2),
                            "same_bjd": prev_row["bjd_code"] == next_row["bjd_code"],
                            "review_flag": score < FUZZY_MATCH_THRESHOLD,
                        }
                    )
    if not candidate_rows:
        return pd.DataFrame(), stats
    candidates = pd.DataFrame(candidate_rows).sort_values("match_confidence", ascending=False)
    accepted_rows = []
    used_prev: set[str] = set()
    used_next: set[str] = set()
    review_rows = []
    for _, row in candidates.iterrows():
        if row["match_confidence"] < FUZZY_MATCH_THRESHOLD:
            review_rows.append(row)
            continue
        if row["from_uid"] in used_prev or row["to_uid"] in used_next:
            continue
        accepted_rows.append(row)
        used_prev.add(row["from_uid"])
        used_next.add(row["to_uid"])
    stats["review_pairs_70_84"] = len(review_rows)
    stats["accepted_pairs_85_plus"] = len(accepted_rows)
    accepted = pd.DataFrame(accepted_rows)
    reviews = pd.DataFrame(review_rows)
    if not reviews.empty:
        safe_to_csv(reviews, V8_TABLES / f"fuzzy_review_pairs_{candidates.iloc[0]['from_snapshot']}_{candidates.iloc[0]['to_snapshot']}.csv")
    return accepted, stats


def match_snapshots(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    logging.info("Matching snapshots")
    all_matches = []
    transition_rows = []
    uf = UnionFind(panel["snapshot_uid"].tolist())
    for idx in range(len(SNAPSHOT_DATES) - 1):
        from_date, to_date = SNAPSHOT_DATES[idx], SNAPSHOT_DATES[idx + 1]
        prev = panel[panel["snapshot_date"] == from_date].copy()
        nxt = panel[panel["snapshot_date"] == to_date].copy()
        direct, direct_prev, direct_next = direct_id_matches(prev, nxt)
        prev_unmatched = prev[~prev["snapshot_uid"].isin(direct_prev)]
        nxt_unmatched = nxt[~nxt["snapshot_uid"].isin(direct_next)]
        fuzzy, fuzzy_stats = fuzzy_block_matches(prev_unmatched, nxt_unmatched)
        transition_matches = pd.concat([direct, fuzzy], ignore_index=True)
        for _, row in transition_matches.iterrows():
            if row["match_confidence"] >= FUZZY_MATCH_THRESHOLD:
                uf.union(row["from_uid"], row["to_uid"])
        all_matches.append(transition_matches)
        transition_rows.append(
            {
                "from_snapshot": from_date,
                "to_snapshot": to_date,
                "from_rows": len(prev),
                "to_rows": len(nxt),
                "direct_id_matches": len(direct),
                "blocked_fuzzy_matches": len(fuzzy),
                "total_matches": len(transition_matches),
                "match_rate_from": round(len(transition_matches) / len(prev), 4) if len(prev) else np.nan,
                "direct_id_match_rate_from": round(len(direct) / len(prev), 4) if len(prev) else np.nan,
                "blocked_fuzzy_match_rate_from": round(len(fuzzy) / len(prev), 4) if len(prev) else np.nan,
                "unmatched_from": len(prev) - len(transition_matches),
                **fuzzy_stats,
                "special_2024_transition": from_date in {"20231231", "20240630"},
            }
        )
        logging.info(
            "Transition %s -> %s: direct=%d fuzzy=%d rate=%.3f",
            from_date,
            to_date,
            len(direct),
            len(fuzzy),
            len(transition_matches) / len(prev),
        )
    match_df = pd.concat(all_matches, ignore_index=True) if all_matches else pd.DataFrame()
    panel = panel.copy()
    panel["matched_store_id"] = panel["snapshot_uid"].map(lambda uid: uf.find(uid))
    transition_df = pd.DataFrame(transition_rows)
    safe_to_csv(match_df, V8_PROCESSED / "snapshot_transition_matches.csv")
    safe_to_csv(transition_df, V8_TABLES / "matching_quality_by_transition.csv")
    return panel, transition_df


def add_labels(panel: pd.DataFrame) -> pd.DataFrame:
    logging.info("Adding observation-retention proxy labels")
    by_group = panel.groupby("matched_store_id")["snapshot_date"].apply(set).to_dict()
    prev_map = {SNAPSHOT_DATES[i]: SNAPSHOT_DATES[i - 1] for i in range(1, len(SNAPSHOT_DATES))}
    plus6_map = {SNAPSHOT_DATES[i]: SNAPSHOT_DATES[i + 1] for i in range(len(SNAPSHOT_DATES) - 1)}
    plus12_map = {SNAPSHOT_DATES[i]: SNAPSHOT_DATES[i + 2] for i in range(len(SNAPSHOT_DATES) - 2)}
    panel = panel.copy()
    panel["survived_6m"] = np.nan
    panel["survived_12m"] = np.nan
    panel["is_new_store_t"] = np.nan
    panel["new_store_survived_12m"] = np.nan
    for idx, row in panel.iterrows():
        dates = by_group.get(row["matched_store_id"], set())
        cur = row["snapshot_date"]
        if cur in plus6_map:
            panel.at[idx, "survived_6m"] = int(plus6_map[cur] in dates)
        if cur in plus12_map:
            panel.at[idx, "survived_12m"] = int(plus12_map[cur] in dates)
        if cur in prev_map:
            is_new = int(prev_map[cur] not in dates)
            panel.at[idx, "is_new_store_t"] = is_new
            if is_new and cur in plus12_map:
                panel.at[idx, "new_store_survived_12m"] = int(plus12_map[cur] in dates)
    safe_to_csv(panel, V8_PROCESSED / "matched_store_panel.csv")
    label_summary = []
    for target in ["survived_6m", "survived_12m", "new_store_survived_12m"]:
        valid = panel[target].dropna()
        label_summary.append(
            {
                "internal_column": target,
                "report_expression": {
                    "survived_6m": "6개월 영업 유지 proxy",
                    "survived_12m": "12개월 영업 유지 proxy",
                    "new_store_survived_12m": "신규 점포 12개월 관측 유지 proxy",
                }[target],
                "valid_rows": len(valid),
                "positive_rate": round(float(valid.mean()), 4) if len(valid) else np.nan,
            }
        )
    safe_to_csv(pd.DataFrame(label_summary), V8_TABLES / "label_summary.csv")
    return panel


def load_static_support() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bus_path = PROJECT_ROOT / "data" / "processed" / "transport_bus_gwangju.csv"
    subway_path = PROJECT_ROOT / "data" / "processed" / "subway_gwangju.csv"
    land_path = PROJECT_ROOT / "data" / "processed" / "land_price_dong_summary.csv"
    trade_path = PROJECT_ROOT / "data" / "processed" / "real_trade_dong_summary.csv"
    bus = pd.read_csv(bus_path) if bus_path.exists() else pd.DataFrame()
    subway = pd.read_csv(subway_path) if subway_path.exists() else pd.DataFrame()
    land = pd.read_csv(land_path, dtype={"bjd_code": str, "sigungu_code": str}) if land_path.exists() else pd.DataFrame()
    trade = pd.read_csv(trade_path, dtype={"sigungu_code": str}) if trade_path.exists() else pd.DataFrame()
    return bus, subway, land, trade


def add_nearest_features(df: pd.DataFrame, points: pd.DataFrame, prefix: str, radii: list[int]) -> pd.DataFrame:
    df = df.copy()
    if points.empty:
        df[f"nearest_{prefix}_m"] = np.nan
        for radius in radii:
            df[f"{prefix}_count_{radius}m"] = 0
        return df
    points = points.dropna(subset=["lon", "lat"]).copy()
    if points.empty:
        return add_nearest_features(df, pd.DataFrame(), prefix, radii)
    px, py = lonlat_to_xy(points["lon"], points["lat"])
    tree = BallTree(np.column_stack([px, py]), metric="euclidean")
    xy = df[["x_m", "y_m"]].to_numpy(dtype=float)
    dist, _ = tree.query(xy, k=1)
    df[f"nearest_{prefix}_m"] = dist[:, 0]
    for radius in radii:
        df[f"{prefix}_count_{radius}m"] = tree.query_radius(xy, r=radius, count_only=True)
    return df


def add_snapshot_spatial_features(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    out = snapshot_df.copy()
    xy = out[["x_m", "y_m"]].to_numpy(dtype=float)
    tree = BallTree(xy, metric="euclidean")
    for radius in RADIUS_M:
        out[f"total_store_{radius}m"] = tree.query_radius(xy, r=radius, count_only=True)
    out["industry_entropy_500m"] = 0.0
    out["hhi_500m"] = 1.0
    idx_500 = tree.query_radius(xy, r=500)
    industry_codes = out["industry_group"].astype("category")
    code_values = industry_codes.cat.codes.to_numpy()
    for i, neighbors in enumerate(idx_500):
        if len(neighbors) == 0:
            continue
        sample_idx = neighbors[:500]
        counts = np.bincount(code_values[sample_idx], minlength=len(industry_codes.cat.categories))
        counts = counts[counts > 0]
        p = counts / counts.sum()
        out.iat[i, out.columns.get_loc("hhi_500m")] = float(np.square(p).sum())
        out.iat[i, out.columns.get_loc("industry_entropy_500m")] = float(-(p * np.log(p + 1e-12)).sum())
    for industry, block in out.groupby("industry_group"):
        block_xy = block[["x_m", "y_m"]].to_numpy(dtype=float)
        block_tree = BallTree(block_xy, metric="euclidean")
        block_counts = {}
        for radius in RADIUS_M:
            block_counts[radius] = block_tree.query_radius(block_xy, r=radius, count_only=True) - 1
        for radius, counts in block_counts.items():
            out.loc[block.index, f"same_industry_{radius}m_excl_self"] = counts
    return out


def build_feature_datasets(panel: pd.DataFrame) -> pd.DataFrame:
    logging.info("Building v8 feature datasets")
    bus, subway, land, trade = load_static_support()
    frames = []
    for snapshot_date in SNAPSHOT_DATES:
        snap = panel[panel["snapshot_date"] == snapshot_date].copy()
        if snap.empty:
            continue
        snap = add_snapshot_spatial_features(snap)
        snap = add_nearest_features(snap, bus, "bus", [300, 500])
        snap = add_nearest_features(snap, subway, "subway", [500])
        frames.append(snap)
        logging.info("Feature snapshot %s rows=%d", snapshot_date, len(snap))
    features = pd.concat(frames, ignore_index=True)
    if not land.empty:
        features = features.merge(
            land[["bjd_code", "avg_land_price_dong", "median_land_price_dong"]],
            on="bjd_code",
            how="left",
        )
    else:
        features["avg_land_price_dong"] = np.nan
        features["median_land_price_dong"] = np.nan
    if not trade.empty:
        trade_gu = (
            trade.groupby("sigungu_code")
            .agg(
                transaction_price_mean_gu=("trade_price_median_dong", "mean"),
                transaction_price_per_area_mean_gu=("trade_price_per_area_median_dong", "mean"),
            )
            .reset_index()
        )
        features = features.merge(trade_gu, on="sigungu_code", how="left")
    else:
        features["transaction_price_mean_gu"] = np.nan
        features["transaction_price_per_area_mean_gu"] = np.nan
    features["cost_burden_proxy"] = features["median_land_price_dong"].fillna(features["transaction_price_mean_gu"])
    features["cost_proxy_type"] = "static cost proxy"
    features["store_name_length"] = features["normalized_name"].str.len()
    first_seen = features.groupby("matched_store_id")["snapshot_date"].transform("min")
    features["first_seen_date"] = first_seen
    features["store_age_proxy_months"] = (
        (features["snapshot_date"].str[:4].astype(int) - first_seen.str[:4].astype(int)) * 12
        + (features["snapshot_date"].str[4:6].astype(int) - first_seen.str[4:6].astype(int))
    )
    safe_to_csv(features, V8_ANALYSIS / "feature_store_level.csv")
    safe_to_csv(features[features["survived_6m"].notna()], V8_ANALYSIS / "survival_6m_dataset.csv")
    safe_to_csv(features[features["survived_12m"].notna()], V8_ANALYSIS / "survival_12m_dataset.csv")
    safe_to_csv(features[features["new_store_survived_12m"].notna()], V8_ANALYSIS / "new_store_survival_12m_dataset.csv")
    return features


BASE_FEATURES = [
    "total_store_100m",
    "total_store_300m",
    "total_store_500m",
    "total_store_1000m",
    "same_industry_100m_excl_self",
    "same_industry_300m_excl_self",
    "same_industry_500m_excl_self",
    "same_industry_1000m_excl_self",
    "industry_entropy_500m",
    "hhi_500m",
    "nearest_bus_m",
    "bus_count_300m",
    "bus_count_500m",
    "nearest_subway_m",
    "subway_count_500m",
    "avg_land_price_dong",
    "median_land_price_dong",
    "transaction_price_mean_gu",
    "transaction_price_per_area_mean_gu",
    "cost_burden_proxy",
    "store_name_length",
    "store_age_proxy_months",
]


def sample_model_rows(df: pd.DataFrame, target: str) -> pd.DataFrame:
    valid = df[df[target].notna()].copy()
    if len(valid) <= MAX_MODEL_ROWS:
        return valid
    parts = []
    group_cols = ["snapshot_date", "sigungu_code", target]
    per_group = max(50, MAX_MODEL_ROWS // max(1, valid.groupby(group_cols, dropna=False).ngroups))
    for _, group in valid.groupby(group_cols, dropna=False):
        n = min(len(group), per_group)
        parts.append(group.sample(n=n, random_state=RANDOM_STATE))
    sampled = pd.concat(parts, ignore_index=True)
    if len(sampled) > MAX_MODEL_ROWS:
        sampled = sampled.sample(n=MAX_MODEL_ROWS, random_state=RANDOM_STATE)
    return sampled


def make_models(y_train: pd.Series) -> dict[str, Any]:
    models: dict[str, Any] = {}
    models["majority_baseline"] = None
    models["rule_baseline"] = None
    models["logistic_regression"] = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=500, class_weight="balanced", random_state=RANDOM_STATE)),
        ]
    )
    models["random_forest"] = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=45,
                    max_depth=8,
                    min_samples_leaf=10,
                    class_weight="balanced_subsample",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    if XGBClassifier is not None:
        pos = max(int((y_train == 1).sum()), 1)
        neg = max(int((y_train == 0).sum()), 1)
        models["xgboost"] = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    XGBClassifier(
                        n_estimators=55,
                        max_depth=3,
                        learning_rate=0.07,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        eval_metric="logloss",
                        tree_method="hist",
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                        scale_pos_weight=neg / pos,
                    ),
                ),
            ]
        )
    if lgb is not None:
        models["lightgbm"] = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", lgb.LGBMClassifier(n_estimators=80, random_state=RANDOM_STATE, class_weight="balanced")),
            ]
        )
    return models


def evaluate_predictions(y_true: pd.Series, pred: np.ndarray, proba: np.ndarray) -> dict[str, Any]:
    out: dict[str, Any] = {
        "rows": int(len(y_true)),
        "positive_rate": round(float(y_true.mean()), 4) if len(y_true) else np.nan,
        "accuracy": round(float(accuracy_score(y_true, pred)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
    }
    try:
        out["auroc"] = round(float(roc_auc_score(y_true, proba)), 4)
    except Exception:
        out["auroc"] = np.nan
    try:
        out["pr_auc"] = round(float(average_precision_score(y_true, proba)), 4)
    except Exception:
        out["pr_auc"] = np.nan
    try:
        out["brier_score"] = round(float(brier_score_loss(y_true, proba)), 4)
    except Exception:
        out["brier_score"] = np.nan
    return out


def fit_eval_split(
    df: pd.DataFrame,
    target: str,
    split_name: str,
    train_mask: pd.Series,
    test_mask: pd.Series,
    features: list[str],
    model_names: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    train = df[train_mask & df[target].notna()].copy()
    test = df[test_mask & df[target].notna()].copy()
    if train.empty or test.empty or train[target].nunique() < 2 or test[target].nunique() < 2:
        return [], None
    X_train = train[features].apply(pd.to_numeric, errors="coerce")
    X_test = test[features].apply(pd.to_numeric, errors="coerce")
    y_train = train[target].astype(int)
    y_test = test[target].astype(int)
    rows = []
    best_model = None
    best_score = -1.0
    majority = int(y_train.mean() >= 0.5)
    rule_score = (
        minmax_scale_safe(test["total_store_300m"])
        + minmax_scale_safe(test["bus_count_300m"])
        + minmax_scale_safe(test["cost_burden_proxy"], invert=True)
    ) / 3
    baselines = {
        "majority_baseline": (np.full(len(y_test), majority), np.full(len(y_test), float(majority))),
        "rule_baseline": ((rule_score >= rule_score.median()).astype(int).to_numpy(), (rule_score / 100).to_numpy()),
    }
    for model_name, (pred, proba) in baselines.items():
        metric = evaluate_predictions(y_test, pred, proba)
        metric.update({"target": target, "split": split_name, "model": model_name})
        rows.append(metric)
    requested_models = model_names or {"logistic_regression", "random_forest", "xgboost"}
    for model_name, model in make_models(y_train).items():
        if model is None:
            continue
        if model_name not in requested_models:
            continue
        try:
            model.fit(X_train, y_train)
            proba = model.predict_proba(X_test)[:, 1]
            pred = (proba >= 0.5).astype(int)
            metric = evaluate_predictions(y_test, pred, proba)
            metric.update({"target": target, "split": split_name, "model": model_name})
            rows.append(metric)
            score = metric.get("pr_auc")
            if pd.notna(score) and score > best_score:
                best_score = float(score)
                best_model = {"model": model, "features": features, "target": target, "split": split_name}
        except Exception as exc:
            rows.append({"target": target, "split": split_name, "model": model_name, "error": str(exc)})
    return rows, best_model


def time_split_masks(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    train_dates = {"20220630", "20221231", "20230630", "20231231"}
    test_dates = {"20240630", "20241231"}
    snapshot_dates = df["snapshot_date"].astype(str)
    return snapshot_dates.isin(train_dates), snapshot_dates.isin(test_dates)


def run_model_experiments(features_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    logging.info("Running v8 model experiments")
    features = [f for f in BASE_FEATURES if f in features_df.columns and features_df[f].notna().any()]
    all_metrics = []
    best_model_payload = None
    for target in ["survived_6m", "survived_12m", "new_store_survived_12m"]:
        df = sample_model_rows(features_df, target)
        if df.empty:
            continue
        train_mask, test_mask = time_split_masks(df)
        rows, best = fit_eval_split(df, target, "time_split", train_mask, test_mask, features)
        all_metrics.extend(rows)
        if target == "survived_12m" and best is not None:
            best_model_payload = best
        if target == "survived_12m":
            for sigungu in sorted(df["sigungu_code"].dropna().unique()):
                train_mask = df["sigungu_code"] != sigungu
                test_mask = df["sigungu_code"] == sigungu
                rows, _ = fit_eval_split(df, target, f"spatial_holdout_{GWANGJU_SIGUNGU_NAMES.get(sigungu, sigungu)}", train_mask, test_mask, features)
                all_metrics.extend(rows)
            valid = df[df[target].notna()].copy()
            if valid["matched_store_id"].nunique() >= 5:
                groups = valid["matched_store_id"].astype(str)
                gkf = GroupKFold(n_splits=min(3, valid["matched_store_id"].nunique()))
                for fold, (train_idx, test_idx) in enumerate(gkf.split(valid, valid[target].astype(int), groups), start=1):
                    fold_train = pd.Series(False, index=valid.index)
                    fold_test = pd.Series(False, index=valid.index)
                    fold_train.iloc[train_idx] = True
                    fold_test.iloc[test_idx] = True
                    rows, _ = fit_eval_split(valid, target, f"matched_store_id_groupkfold_{fold}", fold_train, fold_test, features)
                    all_metrics.extend(rows)
    metrics_df = pd.DataFrame(all_metrics)
    safe_to_csv(metrics_df, V8_TABLES / "model_metrics.csv")
    if best_model_payload is not None:
        joblib.dump(best_model_payload, V8_TABLES / "best_v8_model.joblib")
    importance = build_feature_importance(best_model_payload, features)
    safe_to_csv(importance, V8_TABLES / "feature_importance.csv")
    return metrics_df, importance


def build_feature_importance(best_model_payload: dict[str, Any] | None, features: list[str]) -> pd.DataFrame:
    if best_model_payload is None:
        return pd.DataFrame({"feature": features, "importance": np.zeros(len(features))})
    model = best_model_payload["model"]
    estimator = model.named_steps.get("model") if isinstance(model, Pipeline) else model
    if hasattr(estimator, "feature_importances_"):
        values = estimator.feature_importances_
    elif hasattr(estimator, "coef_"):
        values = np.abs(estimator.coef_[0])
    else:
        values = np.zeros(len(features))
    return pd.DataFrame({"feature": features, "importance": values}).sort_values("importance", ascending=False)


def retention_rate_table(df: pd.DataFrame, target: str, value_col: str, bins: int = 5) -> pd.DataFrame:
    valid = df[df[target].notna() & df[value_col].notna()].copy()
    if valid.empty or valid[value_col].nunique() < 2:
        return pd.DataFrame()
    valid["bin"] = pd.qcut(valid[value_col].rank(method="first"), bins, labels=False, duplicates="drop") + 1
    return (
        valid.groupby("bin")
        .agg(
            rows=(target, "size"),
            proxy_retention_rate=(target, "mean"),
            value_min=(value_col, "min"),
            value_median=(value_col, "median"),
            value_max=(value_col, "max"),
        )
        .reset_index()
    )


def hypothesis_and_sensitivity(features_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    logging.info("Running hypothesis tables")
    competition_rows = []
    for radius in [100, 300, 500, 1000]:
        col = f"same_industry_{radius}m_excl_self"
        for target in ["survived_6m", "survived_12m"]:
            tab = retention_rate_table(features_df, target, col, bins=5)
            if not tab.empty:
                tab["target"] = target
                tab["radius_m"] = radius
                competition_rows.append(tab)
    competition = pd.concat(competition_rows, ignore_index=True) if competition_rows else pd.DataFrame()
    safe_to_csv(competition, V8_TABLES / "competition_threshold.csv")

    cost_rows = []
    for target in ["survived_6m", "survived_12m"]:
        tab = retention_rate_table(features_df, target, "cost_burden_proxy", bins=5)
        if not tab.empty:
            tab["target"] = target
            cost_rows.append(tab)
    cost = pd.concat(cost_rows, ignore_index=True) if cost_rows else pd.DataFrame()
    safe_to_csv(cost, V8_TABLES / "cost_burden_quantiles.csv")

    radius_rows = []
    for radius in [100, 300, 500, 1000]:
        radius_features = [
            f"total_store_{radius}m",
            f"same_industry_{radius}m_excl_self",
            "nearest_bus_m",
            "bus_count_300m",
            "cost_burden_proxy",
        ]
        radius_features = [c for c in radius_features if c in features_df.columns and features_df[c].notna().any()]
        df = sample_model_rows(features_df, "survived_12m")
        train_mask, test_mask = time_split_masks(df)
        rows, _ = fit_eval_split(
            df,
            "survived_12m",
            f"radius_{radius}m_time_split",
            train_mask,
            test_mask,
            radius_features,
            model_names={"logistic_regression", "random_forest"},
        )
        for row in rows:
            if row.get("model") in {"logistic_regression", "random_forest"}:
                row["radius_m"] = radius
                radius_rows.append(row)
    radius_df = pd.DataFrame(radius_rows)
    safe_to_csv(radius_df, V8_TABLES / "radius_sensitivity.csv")

    ablation_rows = []
    groups = {
        "without_competition": [c for c in BASE_FEATURES if not c.startswith("same_industry")],
        "without_transit": [c for c in BASE_FEATURES if "bus" not in c and "subway" not in c],
        "without_cost": [c for c in BASE_FEATURES if "price" not in c and "cost" not in c and "transaction" not in c],
    }
    df = sample_model_rows(features_df, "survived_12m")
    train_mask, test_mask = time_split_masks(df)
    for name, cols in groups.items():
        cols = [c for c in cols if c in df.columns and df[c].notna().any()]
        rows, _ = fit_eval_split(
            df,
            "survived_12m",
            f"ablation_{name}",
            train_mask,
            test_mask,
            cols,
            model_names={"logistic_regression", "random_forest"},
        )
        ablation_rows.extend(rows)
    ablation = pd.DataFrame(ablation_rows)
    safe_to_csv(ablation, V8_TABLES / "ablation_study.csv")
    return competition, cost, radius_df


def build_industry_and_web_outputs(features_df: pd.DataFrame, metrics_df: pd.DataFrame, importance: pd.DataFrame) -> None:
    features_df = features_df.copy()
    features_df["snapshot_date"] = features_df["snapshot_date"].astype(str)
    latest = features_df[features_df["snapshot_date"] == SNAPSHOT_DATES[-1]].copy()
    valid12 = features_df[features_df["survived_12m"].notna()].copy()
    industry_perf = (
        valid12.groupby("industry_group")
        .agg(
            rows=("survived_12m", "size"),
            retention_proxy_rate=("survived_12m", "mean"),
            avg_total_store_300m=("total_store_300m", "mean"),
            avg_same_industry_300m=("same_industry_300m_excl_self", "mean"),
        )
        .reset_index()
        .sort_values("rows", ascending=False)
    )
    safe_to_csv(industry_perf, V8_TABLES / "industry_performance.csv")

    latest["demand_proxy_score"] = (
        0.6 * minmax_scale_safe(latest["total_store_300m"]) + 0.4 * minmax_scale_safe(latest["industry_entropy_500m"])
    )
    latest["competition_burden_score"] = minmax_scale_safe(latest["same_industry_300m_excl_self"], invert=True)
    latest["accessibility_score"] = (
        0.5 * minmax_scale_safe(latest["nearest_bus_m"], invert=True) + 0.5 * minmax_scale_safe(latest["bus_count_300m"])
    )
    latest["cost_score"] = minmax_scale_safe(latest["cost_burden_proxy"], invert=True)
    latest["industry_fit_score"] = latest["industry_group"].map(
        industry_perf.set_index("industry_group")["retention_proxy_rate"].to_dict()
    )
    latest["industry_fit_score"] = minmax_scale_safe(latest["industry_fit_score"])
    latest["retention_proxy_score"] = (
        0.30 * latest["demand_proxy_score"]
        + 0.25 * latest["competition_burden_score"]
        + 0.15 * latest["accessibility_score"]
        + 0.15 * latest["cost_score"]
        + 0.15 * latest["industry_fit_score"]
    ).round(2)
    latest["suitability_score"] = latest["retention_proxy_score"]
    latest["risk_level"] = pd.cut(latest["suitability_score"], bins=[-1, 55, 75, 101], labels=["높음", "보통", "낮음"]).astype(str)
    latest["grid_x"] = np.floor(latest["x_m"] / 500).astype(int)
    latest["grid_y"] = np.floor(latest["y_m"] / 500).astype(int)
    latest["candidate_id"] = (
        "GJ-"
        + latest["sigungu_code"].astype(str)
        + "-"
        + latest["grid_x"].astype(str)
        + "-"
        + latest["grid_y"].astype(str)
        + "-"
        + latest["industry_group"].astype(str)
    )
    candidates = (
        latest.sort_values("suitability_score", ascending=False)
        .drop_duplicates(["candidate_id"])
        .head(150)
        .copy()
    )
    candidate_rows = []
    for _, row in candidates.iterrows():
        positive = []
        negative = []
        if row["demand_proxy_score"] >= 65:
            positive.append("상권 규모와 업종 다양성 proxy가 높습니다.")
        else:
            negative.append("상권 규모 proxy가 낮아 수요 검증이 약할 수 있습니다.")
        if row["competition_burden_score"] >= 65:
            positive.append("동일 업종 경쟁 부담 proxy가 과도하지 않습니다.")
        else:
            negative.append("동일 업종 경쟁 부담 proxy가 높은 편입니다.")
        if row["accessibility_score"] >= 65:
            positive.append("대중교통 접근성 proxy가 좋습니다.")
        if row["cost_score"] < 45:
            negative.append("비용 부담 proxy가 높은 편입니다.")
        candidate_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "lat": round(float(row["lat"]), 6),
                "lon": round(float(row["lon"]), 6),
                "sigungu": row["sigungu_name"],
                "dong": row["dong_name"],
                "recommended_industry": row["industry_group"],
                "suitability_score": round(float(row["suitability_score"]), 2),
                "retention_proxy_score": round(float(row["retention_proxy_score"]), 2),
                "risk_level": row["risk_level"],
                "demand_proxy_score": round(float(row["demand_proxy_score"]), 2),
                "competition_burden_score": round(float(row["competition_burden_score"]), 2),
                "accessibility_score": round(float(row["accessibility_score"]), 2),
                "cost_burden_proxy": None if pd.isna(row["cost_burden_proxy"]) else round(float(row["cost_burden_proxy"]), 2),
                "industry_fit_score": round(float(row["industry_fit_score"]), 2),
                "positive_reasons": positive[:3],
                "negative_reasons": negative[:3],
            }
        )
    safe_to_csv(candidates, V8_TABLES / "top_candidates.csv")
    write_json(V8_WEB / "candidates.json", candidate_rows)

    industry_rec_rows = []
    for candidate_id, block in latest.sort_values("suitability_score", ascending=False).groupby(["grid_x", "grid_y"]):
        block = block.drop_duplicates("industry_group").head(5)
        if block.empty:
            continue
        base = block.iloc[0]
        industry_rec_rows.append(
            {
                "candidate_id": f"GJ-{base['sigungu_code']}-{base['grid_x']}-{base['grid_y']}",
                "industry_top5": [
                    {
                        "rank": rank,
                        "industry": r["industry_group"],
                        "score": round(float(r["suitability_score"]), 2),
                        "retention_proxy_score": round(float(r["retention_proxy_score"]), 2),
                        "reason": "상가정보 스냅샷상 관측 유지 proxy와 공공데이터 기반 점수를 함께 반영했습니다.",
                    }
                    for rank, (_, r) in enumerate(block.iterrows(), start=1)
                ],
            }
        )
        if len(industry_rec_rows) >= 100:
            break
    write_json(V8_WEB / "industry_recommendations.json", industry_rec_rows)
    safe_to_csv(pd.json_normalize(industry_rec_rows), V8_TABLES / "top_industry_recommendations.csv")

    district = (
        latest.groupby("sigungu_name")
        .agg(
            candidate_rows=("snapshot_uid", "size"),
            avg_suitability_score=("suitability_score", "mean"),
            avg_retention_proxy_score=("retention_proxy_score", "mean"),
            avg_cost_burden_proxy=("cost_burden_proxy", "mean"),
            avg_same_industry_300m=("same_industry_300m_excl_self", "mean"),
        )
        .reset_index()
    )
    write_json(V8_WEB / "district_summary.json", district.round(4).to_dict("records"))
    write_json(V8_WEB / "model_metrics.json", {"models": metrics_df.fillna("").to_dict("records"), "primary_validation": "time_split, spatial_holdout, matched_store_id GroupKFold"})
    write_json(V8_WEB / "validation_summary.json", build_validation_summary(valid12))
    write_json(V8_WEB / "explanation_rules.json", build_explanation_rules())
    write_json(V8_WEB / "assistant_recommendation_context.json", build_assistant_context(candidate_rows))
    safe_to_csv(district, V8_TABLES / "district_summary.csv")


def build_validation_summary(valid12: pd.DataFrame) -> dict[str, Any]:
    if valid12.empty:
        return {}
    score = (
        minmax_scale_safe(valid12["total_store_300m"])
        + minmax_scale_safe(valid12["same_industry_300m_excl_self"], invert=True)
        + minmax_scale_safe(valid12["bus_count_300m"])
        + minmax_scale_safe(valid12["cost_burden_proxy"], invert=True)
    ) / 4
    try:
        corr, pval = spearmanr(score, valid12["survived_12m"], nan_policy="omit")
    except Exception:
        corr, pval = np.nan, np.nan
    top = valid12[score >= score.quantile(0.8)]["survived_12m"].mean()
    bottom = valid12[score <= score.quantile(0.2)]["survived_12m"].mean()
    return {
        "metric_meaning": "12개월 영업 유지 proxy와 후보지 점수의 보조 검증",
        "spearman_score_vs_retention_proxy": None if pd.isna(corr) else round(float(corr), 4),
        "spearman_p_value": None if pd.isna(pval) else round(float(pval), 6),
        "top_20pct_retention_proxy_rate": None if pd.isna(top) else round(float(top), 4),
        "bottom_20pct_retention_proxy_rate": None if pd.isna(bottom) else round(float(bottom), 4),
        "safe_note": "창업 성공, 폐업, 매출을 직접 예측한 결과가 아닙니다.",
    }


def build_explanation_rules() -> dict[str, Any]:
    return {
        "positive_rules": [
            {"feature": "demand_proxy_score", "condition": ">= 65", "text": "상권 규모와 업종 다양성 proxy가 높습니다."},
            {"feature": "competition_burden_score", "condition": ">= 65", "text": "동일 업종 경쟁 부담 proxy가 과도하지 않습니다."},
            {"feature": "accessibility_score", "condition": ">= 65", "text": "대중교통 접근성 proxy가 좋습니다."},
        ],
        "negative_rules": [
            {"feature": "competition_burden_score", "condition": "< 45", "text": "동일 업종 경쟁 부담 proxy가 높은 편입니다."},
            {"feature": "cost_burden_proxy", "condition": "high quantile", "text": "비용 부담 proxy가 높은 편입니다."},
            {"feature": "demand_proxy_score", "condition": "< 45", "text": "수요 가능성 proxy가 낮아 추가 확인이 필요합니다."},
        ],
        "safe_answer_guideline": "창업 성공을 보장하지 않고, 상가정보 스냅샷상 관측 유지와 공공데이터 proxy 기반 1차 후보지 필터링 결과로 설명할 것",
    }


def build_assistant_context(candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in candidate_rows:
        grouped[row["sigungu"]][row["recommended_industry"]].append(row)
    context = {}
    for sigungu, by_industry in grouped.items():
        context[sigungu] = {}
        for industry, rows in by_industry.items():
            context[sigungu][industry] = rows[:3]
    return {
        "top3_by_region_industry": context,
        "safe_answer_guideline": "창업 성공을 보장하지 않고, 공공데이터 기반 1차 후보지 필터링 결과로 설명할 것",
    }


def generate_reports(
    scan_entries: list[SnapshotEntry],
    transition_df: pd.DataFrame,
    panel: pd.DataFrame,
    features_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    importance: pd.DataFrame,
    competition: pd.DataFrame,
    cost: pd.DataFrame,
    radius_df: pd.DataFrame,
) -> None:
    logging.info("Generating v8 reports")
    label_summary = pd.read_csv(V8_TABLES / "label_summary.csv")
    scan_df = pd.read_csv(V8_TABLES / "data_file_scan.csv")
    special = transition_df[transition_df["special_2024_transition"] == True]  # noqa: E712

    (V8_REPORTS / "matching_quality_report.md").write_text(
        "# 점포 매칭 품질 보고서\n\n"
        "상가업소번호 직접 매칭을 우선하고, 미매칭 점포에 한해 자치구·업종 그룹·좌표 300m 기반 blocking 후 fuzzy matching을 수행했다. 전체 pairwise 비교는 수행하지 않았다.\n\n"
        "## 시점별 매칭률\n\n"
        + dataframe_to_markdown(transition_df)
        + "\n\n## 2024년 전후 특이 구간\n\n"
        + dataframe_to_markdown(special)
        + "\n\n2024년 업종코드/업소번호 개편 가능성이 있으므로 위 두 구간의 직접 ID 매칭률과 fuzzy matching 비율을 별도로 확인해야 한다.\n",
        encoding="utf-8",
    )
    (V8_REPORTS / "label_definition_report.md").write_text(
        "# 라벨 정의 보고서\n\n"
        "내부 컬럼명으로 `survived_6m`, `survived_12m`, `new_store_survived_12m`를 사용한다. 그러나 보고서와 웹에서는 각각 “6개월 영업 유지 proxy”, “12개월 영업 유지 proxy”, “신규 점포 12개월 관측 유지 proxy”라고 표현한다.\n\n"
        "이 라벨은 실제 창업 성공, 실제 폐업, 실제 매출을 뜻하지 않는다. 상가정보 스냅샷상 계속 관측되는지를 나타내는 proxy다.\n\n"
        + dataframe_to_markdown(label_summary),
        encoding="utf-8",
    )
    (V8_REPORTS / "feature_design_report.md").write_text(
        "# 피처 설계 보고서\n\n"
        "모든 feature는 시점 t 또는 t 이전 정보만 사용한다. t+6, t+12 정보는 영업 유지 proxy 라벨 생성에만 사용하며 feature에는 포함하지 않는다.\n\n"
        "공시지가와 실거래가가 연도별로 엄밀히 매칭되지 않은 경우에는 `static cost proxy`로만 표시하고, 시점별 인과 효과처럼 해석하지 않는다.\n\n"
        "주요 feature군은 상권 규모, 동일 업종 경쟁, 업종 다양성, 교통 접근성, 비용 부담 proxy, 점포 자체 변수다.\n",
        encoding="utf-8",
    )
    primary_metrics = metrics_df[metrics_df["split"].astype(str).str.contains("time_split|spatial_holdout|groupkfold", regex=True, na=False)]
    (V8_REPORTS / "model_validation_report.md").write_text(
        "# 모델 검증 보고서\n\n"
        "최종 성능은 random split이 아니라 time split, spatial holdout, matched_store_id GroupKFold 결과를 우선한다. 본 실험은 매출 예측이 아니며, 창업 성공 또는 실제 폐업을 예측하지 않는다.\n\n"
        f"계산 시간을 통제하기 위해 모델 학습/검증은 타깃별 최대 {MAX_MODEL_ROWS:,}행 균형 샘플로 수행했다. 전체 라벨 데이터셋과 매칭/가설 검증 표는 별도 산출물에 보존했다.\n\n"
        "## 주요 성능표\n\n"
        + dataframe_to_markdown(primary_metrics)
        + "\n\n## Feature Importance\n\n"
        + dataframe_to_markdown(importance.head(20)),
        encoding="utf-8",
    )
    (V8_REPORTS / "hypothesis_validation_report.md").write_text(
        "# 가설 검증 보고서\n\n"
        "## H2 경쟁 임계점\n\n"
        "H2는 모델 feature importance가 아니라 동일 업종 경쟁도 구간별 6개월/12개월 영업 유지 proxy 비율로 검증한다.\n\n"
        + dataframe_to_markdown(competition.head(60))
        + "\n\n## H3 비용 부담\n\n"
        "H3는 비용 부담 proxy 분위수별 영업 유지 proxy 비율과 비용 변수 제거 ablation으로 검증한다.\n\n"
        + dataframe_to_markdown(cost.head(40))
        + "\n\n## H6 반경 민감도\n\n"
        + dataframe_to_markdown(radius_df.head(80)),
        encoding="utf-8",
    )
    (V8_REPORTS / "web_data_contract.md").write_text(
        "# 웹 데이터 계약\n\n"
        "웹 구현 파일은 만들지 않는다. 대신 웹이 소비할 수 있는 안전한 JSON 계약만 생성한다.\n\n"
        "## 허용 필드명\n\n"
        "`retention_proxy_score`, `suitability_score`, `cost_burden_proxy`, `demand_proxy_score`, `competition_burden_score`, `accessibility_score`, `industry_fit_score`, `risk_level`, `positive_reasons`, `negative_reasons`\n\n"
        "## 금지 필드명\n\n"
        "`success_probability`, `survival_probability`, `failure_probability`, `closure_probability`, `sales_prediction`, `revenue_prediction`\n\n"
        "## 필수 문구\n\n"
        "- 이 점수는 창업 성공을 보장하지 않습니다.\n"
        "- 상가정보 스냅샷상 관측 유지와 공공데이터 proxy를 기반으로 후보지를 비교하기 위한 1차 필터링 지표입니다.\n"
        "- 실제 창업 판단에는 임대료, 권리금, 점포 내부 상태, 브랜드 전략, 실제 유동인구 등 추가 확인이 필요합니다.\n",
        encoding="utf-8",
    )
    (V8_REPORTS / "risk_checklist.md").write_text(
        "# 리스크 체크리스트\n\n"
        "- [x] 내부 라벨명을 외부 표현으로 직접 노출하지 않는다.\n"
        "- [x] 2024년 전후 매칭률을 별도 보고한다.\n"
        "- [x] fuzzy matching은 blocking 후 수행한다.\n"
        "- [x] t+6, t+12 정보는 feature에 포함하지 않는다.\n"
        "- [x] 비용 변수는 static cost proxy로 표시한다.\n"
        "- [x] H2는 경쟁도 구간별 유지율로 검증한다.\n"
        "- [x] H3는 분위수별 유지율과 ablation으로 검증한다.\n"
        "- [x] 최종 모델 성능은 time/spatial/group 결과를 우선한다.\n"
        "- [x] 웹 JSON에 성공/폐업/매출 예측 필드명을 쓰지 않는다.\n"
        "- [x] 본 실험은 매출 예측이 아니다.\n",
        encoding="utf-8",
    )
    summary = [
        "# v8 실험 요약",
        "",
        "이번 실험은 2022~2025 반기별 상가정보 스냅샷을 이용해 상가정보 스냅샷상 관측 유지 패턴을 검증했다.",
        "",
        "## 데이터 스캔",
        dataframe_to_markdown(scan_df[["snapshot_date", "gwangju_entry", "encoding", "row_count_estimate"]]),
        "",
        "## 라벨 요약",
        dataframe_to_markdown(label_summary),
        "",
        "## 매칭 요약",
        dataframe_to_markdown(transition_df[["from_snapshot", "to_snapshot", "match_rate_from", "direct_id_match_rate_from", "blocked_fuzzy_match_rate_from", "special_2024_transition"]]),
        "",
        f"모델 검증은 타깃별 최대 {MAX_MODEL_ROWS:,}행 균형 샘플을 사용했다. 전체 전처리/라벨 CSV는 별도 파일로 보존했다.",
        "",
        "본 실험은 창업 성공, 실제 폐업, 매출을 예측하지 않는다. 결과는 영업 유지 proxy 기반 의사결정 보조 지표로만 해석한다.",
    ]
    (V8_REPORTS / "experiment_summary.md").write_text("\n".join(summary), encoding="utf-8")


def validate_web_json_names() -> list[str]:
    forbidden = [
        "success_probability",
        "survival_probability",
        "failure_probability",
        "closure_probability",
        "sales_prediction",
        "revenue_prediction",
    ]
    violations = []
    for path in V8_WEB.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        for term in forbidden:
            if term in text:
                violations.append(f"{path.name}: {term}")
    (V8_REPORTS / "web_json_field_validation.md").write_text(
        "# 웹 JSON 필드명 검증\n\n"
        + ("금지 필드명 위반 없음.\n" if not violations else "\n".join(f"- {v}" for v in violations)),
        encoding="utf-8",
    )
    return violations


def run_v8(mode: str = "all") -> None:
    setup_v8_logging()
    ensure_v8_dirs()
    if mode == "scan":
        scan_snapshots()
        return

    if mode == "all":
        entries = scan_snapshots()
        panel = build_store_panel(entries)
        matched_panel, transition_df = match_snapshots(panel)
        matched_panel = add_labels(matched_panel)
        features_df = build_feature_datasets(matched_panel)
    else:
        entries = scan_snapshots()
        transition_df = pd.read_csv(V8_TABLES / "matching_quality_by_transition.csv")
        for col in ["from_snapshot", "to_snapshot"]:
            if col in transition_df.columns:
                transition_df[col] = transition_df[col].astype(str)
        matched_panel = pd.DataFrame()
        features_df = pd.read_csv(V8_ANALYSIS / "feature_store_level.csv", low_memory=False)
        if "snapshot_date" in features_df.columns:
            features_df["snapshot_date"] = features_df["snapshot_date"].astype(str)

    if mode in {"reports"}:
        metrics_df = pd.read_csv(V8_TABLES / "model_metrics.csv")
        importance = pd.read_csv(V8_TABLES / "feature_importance.csv")
        competition = pd.read_csv(V8_TABLES / "competition_threshold.csv")
        cost = pd.read_csv(V8_TABLES / "cost_burden_quantiles.csv")
        radius_df = pd.read_csv(V8_TABLES / "radius_sensitivity.csv")
    else:
        metrics_df, importance = run_model_experiments(features_df)
        competition, cost, radius_df = hypothesis_and_sensitivity(features_df)

    build_industry_and_web_outputs(features_df, metrics_df, importance)
    generate_reports(entries, transition_df, matched_panel, features_df, metrics_df, importance, competition, cost, radius_df)
    violations = validate_web_json_names()
    if violations:
        raise RuntimeError(f"웹 JSON 금지 필드명 위반: {violations}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scan", "all", "models", "reports"], default="all")
    args = parser.parse_args(argv)
    run_v8(args.mode)


if __name__ == "__main__":
    main()
