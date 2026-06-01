"""FinBERT news-sentiment scoring CLI for RenQuant news caches."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterator, Protocol

import pandas as pd


log = logging.getLogger("renquant_model_common.news_sentiment_finbert")

DEFAULT_BATCH_SIZE = 64
POS_THRESHOLD = 0.2
NEG_THRESHOLD = -0.2
SAT_FRACTION_LIMIT = 0.95
ZERO_FRACTION_LIMIT = 0.95


class BatchScorer(Protocol):
    def score_batch(self, texts: list[str]) -> list[float]:
        ...


def probs_to_signed(p_pos: float, p_neu: float, p_neg: float) -> float:
    """Convert FinBERT 3-class probabilities to a signed score in [-1, 1]."""
    _ = p_neu
    return float(p_pos - p_neg)


def is_skippable_text(text) -> bool:
    if text is None:
        return True
    return len(str(text).strip()) == 0


def chunk(items: list, size: int) -> Iterator[list]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def aggregate_daily(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate article-level sentiment to per-symbol daily features."""
    if frame.empty:
        return pd.DataFrame(columns=[
            "symbol",
            "date",
            "mean_sentiment",
            "sentiment_dispersion",
            "n_articles",
            "sentiment_pos_share",
            "sentiment_neg_share",
        ])
    grouped = frame.groupby(["symbol", "date"])
    agg = grouped["sentiment"].agg(
        mean_sentiment="mean",
        sentiment_dispersion="std",
        n_articles="count",
    ).reset_index()
    agg["sentiment_dispersion"] = agg["sentiment_dispersion"].fillna(0.0)
    pos = frame[frame["sentiment"] > POS_THRESHOLD].groupby(["symbol", "date"]).size()
    neg = frame[frame["sentiment"] < NEG_THRESHOLD].groupby(["symbol", "date"]).size()
    pos.name = "_n_pos"
    neg.name = "_n_neg"
    agg = agg.merge(pos.reset_index(), on=["symbol", "date"], how="left")
    agg = agg.merge(neg.reset_index(), on=["symbol", "date"], how="left")
    agg["_n_pos"] = agg["_n_pos"].fillna(0)
    agg["_n_neg"] = agg["_n_neg"].fillna(0)
    agg["sentiment_pos_share"] = agg["_n_pos"] / agg["n_articles"]
    agg["sentiment_neg_share"] = agg["_n_neg"] / agg["n_articles"]
    return agg.drop(columns=["_n_pos", "_n_neg"])


def validate_sanity(scores: pd.Series) -> tuple[bool, str]:
    if scores.empty:
        return False, "empty score series"
    n = len(scores)
    n_zero = int((scores == 0.0).sum())
    n_sat_pos = int((scores == 1.0).sum())
    n_sat_neg = int((scores == -1.0).sum())
    if n_zero / n > ZERO_FRACTION_LIMIT:
        return False, f"degenerate: {n_zero}/{n}={n_zero / n:.1%} scores exactly zero"
    if n_sat_pos / n > SAT_FRACTION_LIMIT:
        return False, f"degenerate: {n_sat_pos}/{n}={n_sat_pos / n:.1%} saturated at +1"
    if n_sat_neg / n > SAT_FRACTION_LIMIT:
        return False, f"degenerate: {n_sat_neg}/{n}={n_sat_neg / n:.1%} saturated at -1"
    std = scores.std()
    if pd.notna(std) and std < 1e-6 and n > 1:
        return False, f"constant distribution (std={std:.2e})"
    return True, "ok"


class FinBertScorer:
    """Lazy-loading ProsusAI/finbert scorer."""

    MODEL_NAME = "ProsusAI/finbert"

    def __init__(self, device: str | None = None, max_length: int = 128) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if device is None:
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = device
        self.max_length = int(max_length)
        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.MODEL_NAME).to(device).eval()
        id2label = {int(key): value for key, value in self.model.config.id2label.items()}
        self._idx_pos = next(index for index, label in id2label.items() if label.lower().startswith("pos"))
        self._idx_neg = next(index for index, label in id2label.items() if label.lower().startswith("neg"))
        self._idx_neu = next(index for index, label in id2label.items() if label.lower().startswith("neu"))

    def score_batch(self, texts: list[str]) -> list[float]:
        import torch

        if not texts:
            return []
        cleaned = [text if not is_skippable_text(text) else "neutral" for text in texts]
        skip_mask = [is_skippable_text(text) for text in texts]
        encoded = self.tokenizer(
            cleaned,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with torch.no_grad():
            output = self.model(**encoded)
            probs = torch.softmax(output.logits, dim=-1).cpu().numpy()

        scores: list[float] = []
        for index in range(len(texts)):
            if skip_mask[index]:
                scores.append(0.0)
                continue
            scores.append(probs_to_signed(
                p_pos=float(probs[index][self._idx_pos]),
                p_neu=float(probs[index][self._idx_neu]),
                p_neg=float(probs[index][self._idx_neg]),
            ))
        return scores


def score_one_parquet(
    scorer: BatchScorer,
    in_path: str | Path,
    out_path: str | Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> tuple[int, int, str]:
    """Score one symbol news parquet and write aggregated daily sentiment."""
    in_path = Path(in_path)
    out_path = Path(out_path)
    frame = pd.read_parquet(in_path)
    if frame.empty:
        return 0, 0, "empty"
    texts = frame["headline"].fillna("").astype(str).tolist()
    scores: list[float] = []
    for batch in chunk(texts, batch_size):
        scores.extend(scorer.score_batch(batch))
    frame = frame.copy()
    frame["sentiment"] = scores
    frame["date"] = pd.to_datetime(frame["created_at"], utc=True).dt.date
    frame["date"] = pd.to_datetime(frame["date"])

    ok, reason = validate_sanity(pd.Series(scores))
    if not ok:
        log.warning("%s: sanity failed: %s", in_path.stem, reason)
        return len(texts), 0, reason

    agg = aggregate_daily(frame[["symbol", "date", "sentiment"]])
    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        agg.to_parquet(out_path, index=False)
    return len(texts), len(agg), "ok"


def score_news_sentiment(
    *,
    data_dir: str | Path,
    symbols: list[str] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
    device: str | None = None,
    scorer: BatchScorer | None = None,
) -> dict[str, object]:
    data_dir = Path(data_dir).expanduser().resolve()
    in_dir = data_dir / "news_alpaca"
    out_dir = data_dir / "news_sentiment_alpaca"
    files = sorted(in_dir.glob("*.parquet"))
    if symbols:
        wanted = {symbol.upper() for symbol in symbols}
        files = [path for path in files if path.stem.upper() in wanted]
    scorer = scorer or FinBertScorer(device=device)

    per_symbol: dict[str, dict[str, object]] = {}
    n_articles = 0
    n_files_written = 0
    for path in files:
        out_path = out_dir / f"{path.stem}.parquet"
        articles, days, status = score_one_parquet(
            scorer,
            path,
            out_path,
            batch_size=batch_size,
            dry_run=dry_run,
        )
        n_articles += articles
        if days > 0:
            n_files_written += 1
        per_symbol[path.stem.upper()] = {
            "articles": int(articles),
            "daily_rows": int(days),
            "status": status,
            "path": str(out_path),
        }

    return {
        "ok": True,
        "dry_run": bool(dry_run),
        "n_files": int(len(files)),
        "n_files_written": int(n_files_written),
        "n_articles": int(n_articles),
        "data_dir": str(data_dir),
        "per_symbol": per_symbol,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--device", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    summary = score_news_sentiment(
        data_dir=args.data_dir,
        symbols=[symbol.upper() for symbol in args.symbols] if args.symbols is not None else None,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        device=args.device,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
