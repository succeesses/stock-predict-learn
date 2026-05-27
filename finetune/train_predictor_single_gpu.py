"""
Single-GPU training script for predictor fine-tuning.
This avoids Windows distributed training issues.
"""
import os
import sys
import json
import time
from time import gmtime, strftime
import torch

# ========== Hugging Face SSL 证书修复 ==========
# 解决 "unable to get local issuer certificate" 错误
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # 使用国内镜像
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
# =================================================
from torch.utils.data import DataLoader

# comet_ml is optional, only imported if use_comet=True
try:
    import comet_ml
except ImportError:
    comet_ml = None

# Ensure project root is in path
sys.path.append("../")
from config import Config
from dataset import QlibDataset
from model.kronos import KronosTokenizer, Kronos
# Import shared utilities
from utils.training_utils import (
    set_seed,
    get_model_size,
    format_time
)


def create_dataloaders(config: dict):
    """
    Creates and returns dataloaders for training and validation (single GPU).

    Args:
        config (dict): A dictionary of configuration parameters.

    Returns:
        tuple: (train_loader, val_loader, train_dataset, valid_dataset).
    """
    print("Creating dataloaders...")
    train_dataset = QlibDataset('train')
    valid_dataset = QlibDataset('val')
    print(f"Train dataset size: {len(train_dataset)}, Validation dataset size: {len(valid_dataset)}")

    train_loader = DataLoader(
        train_dataset, batch_size=config['batch_size'], shuffle=True,
        num_workers=config.get('num_workers', 0), pin_memory=True, drop_last=True
    )
    val_loader = DataLoader(
        valid_dataset, batch_size=config['batch_size'], shuffle=False,
        num_workers=config.get('num_workers', 0), pin_memory=True, drop_last=False
    )
    print(f"Dataloaders created. Train steps/epoch: {len(train_loader)}, Val steps: {len(val_loader)}")
    return train_loader, val_loader, train_dataset, valid_dataset


def train_model(model, tokenizer, device, config, save_dir, logger):
    """
    The main training and validation loop for the predictor (single GPU).
    """
    start_time = time.time()
    effective_bs = config['batch_size']
    print(f"Effective BATCHSIZE: {config['batch_size']}")

    train_loader, val_loader, train_dataset, valid_dataset = create_dataloaders(config)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config['predictor_learning_rate'],
        betas=(config['adam_beta1'], config['adam_beta2']),
        weight_decay=config['adam_weight_decay']
    )
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=config['predictor_learning_rate'],
        steps_per_epoch=len(train_loader), epochs=config['epochs'],
        pct_start=0.03, div_factor=10
    )

    best_val_loss = float('inf')
    dt_result = {}
    batch_idx_global = 0
    total_steps_total = config['epochs'] * len(train_loader)

    for epoch_idx in range(config['epochs']):
        epoch_start_time = time.time()
        model.train()

        train_dataset.set_epoch_seed(epoch_idx * 10000)
        valid_dataset.set_epoch_seed(0)

        for i, (batch_x, batch_x_stamp) in enumerate(train_loader):
            batch_x = batch_x.to(device, non_blocking=True)
            batch_x_stamp = batch_x_stamp.to(device, non_blocking=True)

            # Tokenize input data on-the-fly
            with torch.no_grad():
                token_seq_0, token_seq_1 = tokenizer.encode(batch_x, half=True)

            # Prepare inputs and targets for the language model
            token_in = [token_seq_0[:, :-1], token_seq_1[:, :-1]]
            token_out = [token_seq_0[:, 1:], token_seq_1[:, 1:]]

            # Forward pass and loss calculation
            logits = model(token_in[0], token_in[1], batch_x_stamp[:, :-1, :])
            loss, s1_loss, s2_loss = model.head.compute_loss(logits[0], logits[1], token_out[0], token_out[1])

            # Backward pass and optimization
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=3.0)
            optimizer.step()
            scheduler.step()

            # Logging
            if (batch_idx_global + 1) % config['log_interval'] == 0:
                lr = optimizer.param_groups[0]['lr']
                # Calculate ETA (Estimated Time of Arrival)
                steps_done = batch_idx_global + 1
                steps_remaining = total_steps_total - steps_done
                elapsed = time.time() - start_time
                step_time_avg = elapsed / steps_done
                eta_seconds = steps_remaining * step_time_avg
                eta_str = format_time(eta_seconds)

                print(
                    f"[Epoch {epoch_idx + 1}/{config['epochs']}, Step {i + 1}/{len(train_loader)}] "
                    f"LR {lr:.6f}, Loss: {loss.item():.4f}, ETA: {eta_str}"
                )
            if logger:
                lr = optimizer.param_groups[0]['lr']
                logger.log_metric('train_predictor_loss_batch', loss.item(), step=batch_idx_global)
                logger.log_metric('train_S1_loss_each_batch', s1_loss.item(), step=batch_idx_global)
                logger.log_metric('train_S2_loss_each_batch', s2_loss.item(), step=batch_idx_global)
                logger.log_metric('predictor_learning_rate', lr, step=batch_idx_global)

            batch_idx_global += 1

        # --- Validation Loop ---
        model.eval()
        tot_val_loss_sum = 0.0
        val_batches_processed = 0
        with torch.no_grad():
            for batch_x, batch_x_stamp in val_loader:
                batch_x = batch_x.to(device, non_blocking=True)
                batch_x_stamp = batch_x_stamp.to(device, non_blocking=True)

                token_seq_0, token_seq_1 = tokenizer.encode(batch_x, half=True)
                token_in = [token_seq_0[:, :-1], token_seq_1[:, :-1]]
                token_out = [token_seq_0[:, 1:], token_seq_1[:, 1:]]

                logits = model(token_in[0], token_in[1], batch_x_stamp[:, :-1, :])
                val_loss, _, _ = model.head.compute_loss(logits[0], logits[1], token_out[0], token_out[1])

                tot_val_loss_sum += val_loss.item()
                val_batches_processed += 1

        avg_val_loss = tot_val_loss_sum / val_batches_processed if val_batches_processed > 0 else 0

        # --- End of Epoch Summary & Checkpointing ---
        print(f"\n--- Epoch {epoch_idx + 1}/{config['epochs']} Summary ---")
        print(f"Validation Loss: {avg_val_loss:.4f}")
        print(f"Time This Epoch: {format_time(time.time() - epoch_start_time)}")
        print(f"Total Time Elapsed: {format_time(time.time() - start_time)}\n")
        if logger:
            logger.log_metric('val_predictor_loss_epoch', avg_val_loss, epoch=epoch_idx)

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            save_path = f"{save_dir}/checkpoints/best_model"
            model.save_pretrained(save_path)
            print(f"Best model saved to {save_path} (Val Loss: {best_val_loss:.4f})")

    dt_result['best_val_loss'] = best_val_loss
    return dt_result


def main(config: dict):
    """Main function to orchestrate single-GPU/CPU training with macOS MPS support."""
    # Auto-detect best available device
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        print(f"Using device: NVIDIA CUDA ({device})")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
        print(f"Using device: Apple Silicon MPS ({device})")
    else:
        device = torch.device("cpu")
        print(f"Using device: CPU (training will be slow)")
    set_seed(config['seed'], 0)

    save_dir = os.path.join(config['save_path'], config['predictor_save_folder_name'])

    # Logger and summary setup
    comet_logger, master_summary = None, {}
    os.makedirs(os.path.join(save_dir, 'checkpoints'), exist_ok=True)
    master_summary = {
        'start_time': strftime("%Y-%m-%dT%H-%M-%S", gmtime()),
        'save_directory': save_dir,
        'world_size': 1,
    }
    if config['use_comet']:
        comet_logger = comet_ml.Experiment(
            api_key=config['comet_config']['api_key'],
            project_name=config['comet_config']['project_name'],
            workspace=config['comet_config']['workspace'],
        )
        comet_logger.add_tag(config['comet_tag'])
        comet_logger.set_name(config['comet_name'])
        comet_logger.log_parameters(config)
        print("Comet Logger Initialized.")

    # Model Initialization
    tokenizer = KronosTokenizer.from_pretrained(config['finetuned_tokenizer_path'])
    tokenizer.eval().to(device)

    model = Kronos.from_pretrained(config['pretrained_predictor_path'])
    model.to(device)

    print(f"Predictor Model Size: {get_model_size(model)}")

    # Start Training
    dt_result = train_model(
        model, tokenizer, device, config, save_dir, comet_logger
    )

    master_summary['final_result'] = dt_result
    with open(os.path.join(save_dir, 'summary.json'), 'w') as f:
        json.dump(master_summary, f, indent=4)
    print('Training finished. Summary file saved.')
    if comet_logger:
        comet_logger.end()


if __name__ == "__main__":
    config_instance = Config()
    main(config_instance.__dict__)
