@echo off
REM Windows batch script to train tokenizer with correct environment settings
REM You need to manually activate conda first: conda activate kronos
set USE_LIBUV=0
python -m torch.distributed.run --standalone --nproc_per_node=1 train_tokenizer.py
pause
