"""Public behavior of the experiment-only CrossEncoder probe."""

from experiments.cross_encoder_probe import run


class FakeCrossEncoder:
    def predict(self, pairs):
        return [1.0 if document == 'semantic answer' else 0.0
                for _, document in pairs]


def test_probe_reranks_a_wider_candidate_pool_before_final_cutoff():
    corpus = {
        'atoms': [
            {'id': f'n{i}', 'session_id': 'noise', 'content': 'same query noise'}
            for i in range(5)
        ] + [{'id': 'answer', 'session_id': 'target',
              'content': 'semantic answer'}],
        'edges': [],
        'queries': [{
            'text': 'same query',
            'relevant_ids': ['answer'],
            'negative_ids': [f'n{i}' for i in range(5)],
        }],
    }

    result = run(FakeCrossEncoder(), corpus, candidate_pool_size=6, top_k=5)

    assert result['aggregates']['macro_recall'] == 1.0
    assert result['rows'][0]['returned_ids'][0] == 'atom-5'
    assert result['conditions']['candidate_pool_size'] == 6
    assert result['conditions']['top_k'] == 5
