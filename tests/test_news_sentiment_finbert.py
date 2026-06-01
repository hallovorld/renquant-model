from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from renquant_model_common.news_sentiment_finbert import (
    aggregate_daily,
    probs_to_signed,
    score_news_sentiment,
    score_one_parquet,
    validate_sanity,
)


pytest.importorskip("pyarrow")


class FakeScorer:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.offset = 0

    def score_batch(self, texts: list[str]) -> list[float]:
        out = self.scores[self.offset:self.offset + len(texts)]
        self.offset += len(texts)
        return out


def _write_news(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "created_at": [
                "2026-01-01T12:00:00Z",
                "2026-01-01T13:00:00Z",
                "2026-01-02T12:00:00Z",
            ],
            "headline": ["good", "bad", "ok"],
        }
    ).to_parquet(path, index=False)


def test_probs_to_signed_ignores_neutral_probability() -> None:
    assert probs_to_signed(0.7, 0.2, 0.1) == pytest.approx(0.6)


def test_aggregate_daily_builds_sentiment_features() -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2026-01-01", "2026-01-01", "2026-01-02"]),
            "sentiment": [0.5, -0.4, 0.0],
        }
    )

    out = aggregate_daily(frame)

    day1 = out[out["date"] == pd.Timestamp("2026-01-01")].iloc[0]
    assert day1["mean_sentiment"] == pytest.approx(0.05)
    assert day1["n_articles"] == 2
    assert day1["sentiment_pos_share"] == pytest.approx(0.5)
    assert day1["sentiment_neg_share"] == pytest.approx(0.5)


def test_validate_sanity_rejects_degenerate_scores() -> None:
    ok, reason = validate_sanity(pd.Series([0.0] * 100))

    assert ok is False
    assert "exactly zero" in reason


def test_score_one_parquet_writes_daily_sentiment(tmp_path: Path) -> None:
    in_path = tmp_path / "news_alpaca" / "AAA.parquet"
    out_path = tmp_path / "news_sentiment_alpaca" / "AAA.parquet"
    _write_news(in_path)

    articles, days, status = score_one_parquet(
        FakeScorer([0.5, -0.4, 0.1]),
        in_path,
        out_path,
        batch_size=2,
    )

    assert (articles, days, status) == (3, 2, "ok")
    out = pd.read_parquet(out_path)
    assert set(["mean_sentiment", "n_articles", "sentiment_pos_share"]).issubset(out.columns)


def test_score_news_sentiment_filters_symbols(tmp_path: Path) -> None:
    _write_news(tmp_path / "news_alpaca" / "AAA.parquet")
    _write_news(tmp_path / "news_alpaca" / "BBB.parquet")

    summary = score_news_sentiment(
        data_dir=tmp_path,
        symbols=["AAA"],
        scorer=FakeScorer([0.5, -0.4, 0.1]),
    )

    assert summary["ok"] is True
    assert summary["n_files"] == 1
    assert (tmp_path / "news_sentiment_alpaca" / "AAA.parquet").exists()
    assert not (tmp_path / "news_sentiment_alpaca" / "BBB.parquet").exists()
