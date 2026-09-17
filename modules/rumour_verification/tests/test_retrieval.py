from datetime import date

import pytest

from src.corpus import load_corpus, load_rumour_dataset
from src.retrieval_baseline import TfidfRetriever
from src.retrieval_constrained import ConstrainedRetriever, mentioned_companies, normalize_company_name


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


@pytest.fixture(scope="module")
def dataset():
    return load_rumour_dataset()


def test_normalize_company_name_strips_legal_suffix():
    assert normalize_company_name("Adani Enterprises Ltd") == "adani enterprises"
    assert normalize_company_name("One97 Communications Limited") == "one97 communications"


def test_mentioned_companies_finds_named_company(corpus):
    text = "Adani Enterprises shares rally 4% on $686 million investment"
    mentioned = mentioned_companies(text, corpus)
    assert "adani enterprises" in mentioned


def test_baseline_retrieves_something_relevant_for_every_rumour(corpus, dataset):
    retriever = TfidfRetriever(corpus)
    for case in dataset:
        results = retriever.search(case.rumour_text, top_k=5)
        retrieved_ids = [r.filing.filing_id for r in results]
        assert len(retrieved_ids) == 5
        assert all(r.score >= 0 for r in results)


def test_constrained_retrieval_finds_correct_filing_for_every_rumour(corpus, dataset):
    retriever = ConstrainedRetriever(corpus)
    hits = 0
    for case in dataset:
        results = retriever.search(case.rumour_text, rumour_date=case.rumour_date, top_k=5)
        top_ids = [r.filing.filing_id for r in results]
        if case.matching_filing_id in top_ids:
            hits += 1
    # every one of the 11 real cases should have its filing correctly
    # entity/temporally/source matched into the constrained top-5
    assert hits == len(dataset)


def test_source_authority_constraint_excludes_news_article_paraphrase(corpus):
    retriever = ConstrainedRetriever(corpus)
    rumour_text = "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative"

    baseline_ids = {r.filing.filing_id for r in retriever.baseline.search(rumour_text, top_k=5)}
    assert "N003" in baseline_ids  # the near-duplicate news paraphrase is a strong lexical match

    constrained = retriever.search(rumour_text, rumour_date=date(2025, 2, 11), top_k=5)
    constrained_ids = [r.filing.filing_id for r in constrained]
    assert "N003" not in constrained_ids
    assert constrained_ids[0] == "F001"


def test_entity_constraint_excludes_same_topic_different_company(corpus):
    retriever = ConstrainedRetriever(corpus)
    # a rumour explicitly about IndusInd Bank should not surface the
    # textually-similar strategic-partner-talk filings of other companies
    rumour_text = "IndusInd Bank is reportedly in talks to bring in a strategic partner to take a minority stake"
    results = retriever.search(rumour_text, rumour_date=date(2025, 12, 3), top_k=5)
    for r in results:
        assert normalize_company_name(r.filing.company_name) == "indusind bank"


def test_temporal_constraint_excludes_filings_before_rumour_date(corpus):
    retriever = ConstrainedRetriever(corpus)
    # Meridian Textiles has two filings (S001, S009) at different dates;
    # anchoring the rumour date right before S009 should exclude S001.
    results = retriever.explain(
        "Meridian Textiles board meeting to consider results",
        rumour_date=date(2025, 11, 30),
        company_name="Meridian Textiles Ltd",
    )
    by_id = {r.filing.filing_id: r for r in results}
    assert by_id["S001"].checks.temporal_ok is False  # S001 filed 2025-03-10, before the rumour date
    assert by_id["S009"].checks.temporal_ok is True  # S009 filed 2025-12-01, within window after


def test_constrained_result_reasons_are_human_readable(corpus):
    retriever = ConstrainedRetriever(corpus)
    results = retriever.explain("Gensol Engineering IREDA fraud loan", rumour_date=date(2026, 7, 13))
    top = results[0]
    reasons = top.checks.reasons()
    assert len(reasons) == 3
    assert any(r.startswith("entity:") for r in reasons)
    assert any(r.startswith("temporal:") for r in reasons)
    assert any(r.startswith("source:") for r in reasons)
