from eval.evaluate import _rank_of_correct, run_evaluation
from src.corpus import load_corpus, load_rumour_dataset


def test_rank_of_correct_finds_position():
    assert _rank_of_correct(["A", "B", "C"], "B") == 2
    assert _rank_of_correct(["A", "B", "C"], "Z") is None


def test_run_evaluation_produces_bounded_metrics():
    corpus = load_corpus()
    dataset = load_rumour_dataset()

    baseline_metrics, constrained_metrics = run_evaluation(corpus, dataset)

    assert 0.0 <= baseline_metrics.mrr <= 1.0
    assert 0.0 <= constrained_metrics.mrr <= 1.0
    for metrics in (baseline_metrics, constrained_metrics):
        for k, p in metrics.precision_at_k.items():
            assert 0.0 <= p <= 1.0
        for k, h in metrics.hit_rate_at_k.items():
            assert 0.0 <= h <= 1.0


def test_constrained_system_finds_every_labeled_rumour_within_top_5():
    corpus = load_corpus()
    dataset = load_rumour_dataset()
    _, constrained_metrics = run_evaluation(corpus, dataset)

    assert constrained_metrics.hit_rate_at_k[5] == 1.0
