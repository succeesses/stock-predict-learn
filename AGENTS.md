# AGENTS.md — Kronos

High-signal facts supplementing `CLAUDE.md`. Read both.

## Repo layout — non-obvious parts

| Path | What |
|------|------|
| `finetune/` | Qlib-based finetune pipeline. Config-driven by `finetune/config.py` (class `Config`). |
| `finetune_csv/` | **Separate** CSV-based finetune pipeline. Uses `--config config.yaml` (YAML, not the Config class). |
| `qlib-master/` | Vendored qlib source (upstream is `pip install pyqlib`). |
| `justicePlutus/` | Separate A-share analysis + LLM pipeline project, not part of Kronos core. |
| `model/__init__.py` | Exports `Kronos`, `KronosTokenizer`, `KronosPredictor`. Also has `get_model_class()`. |

## Training commands — not just torchrun

**Single GPU** (no torchrun needed):
```bash
python finetune/train_tokenizer_single_gpu.py
python finetune/train_predictor_single_gpu.py
```

**Windows** (run in `finetune/` after `conda activate kronos`):
```bat
train_tokenizer.bat    # sets USE_LIBUV=0 before torchrun
train_predictor.bat
```

**macOS MPS** (Apple Silicon):
```bash
bash setup_macos.sh          # one-time env setup
bash finetune/train_all_macos.sh  # full pipeline: preprocess → tokenizer → predictor → backtest
```

## Finetune pipelines — two flavors

| | `finetune/` (Qlib) | `finetune_csv/` (CSV) |
|---|---|---|
| Config | `config.py` (Python class) | `configs/*.yaml` |
| Data source | Qlib local cache | Any CSV file |
| Preprocess first? | Yes: `python finetune/qlib_data_preprocess.py` | No (reads CSV directly) |
| Entry | `train_tokenizer.py` / `train_predictor.py` | `train_sequential.py --config config.yaml` (or `finetune_tokenizer.py` / `finetune_base_model.py` individually) |

## Tests

```bash
python -m pytest tests/test_kronos_regression.py -v
```

Two tests: `test_kronos_predictor_regression` (parametrized by 512/256 context len, checks `assert_allclose` with `rtol=1e-5`) and `test_kronos_predictor_mse` (compares mean MSE against pinned expected values). Runs on CPU, uses pinned HF revisions for reproducibility. Input CSV in `tests/data/regression_input.csv`.

## Data format

All pipelines expect CSV with columns: `timestamps,open,high,low,close,volume,amount`. `volume` and `amount` can be zero if unavailable. The predictor handles OHLCV internally — only `['open','high','low','close']` are strictly required.

## Qlib price adjustment

Qlib stores unadjusted prices + a separate adjustment factor. All Qlib integration scripts (`prediction_qlib_daily.py`, `get_stock_data_from_qlib.py`) multiply prices by the factor to get forward-adjusted prices. Do not adjust manually — scripts handle it.

## Model context limits

- **Kronos-small / Kronos-base**: `max_context=512`
- **Kronos-mini**: `max_context=2048`
- Setting `lookback > max_context` triggers auto-truncation in `KronosPredictor`

## Embedded projects

- `qlib-master/` is a full vendored copy of Microsoft Qlib, not just configs. Do not edit unless modifying qlib itself.
- `justicePlutus/` is a standalone CLI tool for A-share market analysis (gathering → LLM analysis → multi-channel push). Not Kronos code.

## File organization

Files are organized as follows:

| Path | What |
|------|------|
| `archive/unused_scripts/` | User-created one-off scripts (moved from `examples/`) |
| `archive/documents/` | Tutorials, paper translations, reference docs |
| `archive/generated_outputs/` | Regeneratable artifacts (pickle datasets, prediction outputs, PNG, JSON) |

To regenerate archived data: `python finetune/qlib_data_preprocess.py` for datasets, or re-run the relevant prediction scripts.
