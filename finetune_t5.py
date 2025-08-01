import json
import torch.nn as nn
import torch
import wandb

from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    HfArgumentParser,
    set_seed,
)

from eval import Metrics
from trainer import ToxicTrainer
from data.implicit_dataset import ImplicitDataset, ImplicitReasoningDataset, ImplicitCollator
from data.sbic_dataset import SBICDataset, SBICReasoningDataset, SBICCollator, SBICgiven
from options import ModelArguments, DataTrainingArguments, TrainingArguments


def main():
    parser = HfArgumentParser((ModelArguments, DataTrainingArguments, TrainingArguments))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()

    wandb.init(
    project=data_args.tasks,
    # entity=data_args.wandb_entity,   # 改这里，改成 wandb_entity
    # group=data_args.wandb_group,
    name=data_args.wandb_name,
    mode="online"
    )

    
    # set seed
    set_seed(training_args.seed)
    
    model = AutoModelForSeq2SeqLM.from_pretrained(model_args.model_name_or_path, resume_download=True)
    tokenizer = AutoTokenizer.from_pretrained(model_args.model_name_or_path)

    zero_shot = getattr(training_args, "zero_shot_test", False)
    metrics = Metrics(tokenizer, training_args.output_dir, zero_shot)
    # metrics = Metrics(tokenizer, training_args.output_dir, training_args.zero_shot_test)
        
    if data_args.tasks == "implicit":
        compute_metrics = metrics.compute_implicit_metrics
        
        if data_args.reasoning:
            implicit_dataset = ImplicitReasoningDataset
        else:
            implicit_dataset = ImplicitDataset
        train_dataset = implicit_dataset(data_args.train_data_file)
        valid_dataset = implicit_dataset(data_args.eval_data_file)
        test_dataset = implicit_dataset(data_args.test_data_file)
        data_collator = ImplicitCollator(tokenizer=tokenizer)
        
    elif data_args.tasks == "sbic":
        compute_metrics = metrics.compute_sbic_metrics
        if data_args.reasoning:
            SBIC_dataset = SBICReasoningDataset
            train_dataset = SBIC_dataset(data_args.train_data_file, train=True)
        else:
            SBIC_dataset = SBICDataset if not data_args.cti else SBICgiven
            train_dataset = SBIC_dataset(data_args.train_data_file)
        valid_dataset = SBIC_dataset(data_args.eval_data_file)
        test_dataset = SBIC_dataset(data_args.test_data_file)
        data_collator = SBICCollator(tokenizer=tokenizer)
    
    trainer = ToxicTrainer(
        model=model,
        args=training_args,
        data_collator=data_collator,
        train_dataset=train_dataset,
        eval_dataset=valid_dataset,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    print("Evaluate on test set")
    trainer.evaluate(eval_dataset=test_dataset, metric_key_prefix = 'test')
    
if __name__ == "__main__":
    main()