from src.job_radar.config import INDEX_DIR
from src.job_radar.services.index.inverted_index import InvertedIndex

query = "python разработчик"

idx_plain = InvertedIndex()
idx_plain.load_plain(INDEX_DIR / "index_plain.json")
res_plain = set(idx_plain.search(query))

idx_delta = InvertedIndex()
idx_delta.load_delta(INDEX_DIR / "index_delta.bin")
res_delta = set(idx_delta.search(query))

idx_gamma = InvertedIndex()
idx_gamma.load_gamma(INDEX_DIR / "index_gamma.bin")
res_gamma = set(idx_gamma.search(query))

assert res_plain == res_delta == res_gamma, "Mismatch!"
print(f"OK: все три вернули одинаковое количество ({len(res_plain)}) документов")