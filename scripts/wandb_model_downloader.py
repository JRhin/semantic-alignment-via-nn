"""This python module handles the download of the trained models from wandb.

    To check available parameters run 'python /path/to/wandb_model_downloader.py --help'.
"""
    
import wandb
import shutil
from pathlib import Path
from tqdm.auto import tqdm


def find_and_rename_ckpt_files(root_dir: str,
                               new_dir: str,
                               name: str) -> None:
    """Save the results in a convenient directory structure.

    Args:
        root_dir : str
            The directory where the files are currently saved.
        new_dir : str
            The new directory where to save the files.
        name : str
            The new name of the file.

    Returns:
        None
    """
    root_dir = Path(root_dir)
    new_dir = Path(new_dir)

    # Ensure the new directory exists
    new_dir.mkdir(parents=True, exist_ok=True)

    # Find all .ckpt files in subdirectories
    ckpt_files = list(root_dir.rglob('*.ckpt'))

    new_path = new_dir / f'seed_{name}.ckpt'
    shutil.move(str(ckpt_files[0]), str(new_path))
    print(f'Moved: {ckpt_files[0]} to {new_path}')
    
    return None


        
# ============================================================
#
#                     MAIN DEFINITION
#
# ============================================================

def main() -> None:
    """The main loop.
    """
    import argparse
    
    description = """
    This python module handles the download of the trained models from wandb.

    To check available parameters run 'python /path/to/wandb_model_downloader.py --help'.
    """
    
    parser = argparse.ArgumentParser(description=description,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-o',
                        '--org',
                        help="The organization of wandb where the models are saved.",
                        type=str)
    
    parser.add_argument('--pruned',
                        help="If to download the pruned version of the models or not. Default False.",
                        default=False,
                        type=bool,
                        action=argparse.BooleanOptionalAction)
    
    args = parser.parse_args()

    run = wandb.init()

    seeds = [27, 42, 100, 123, 144, 200]
    antennas = [1, 2, 4, 6, 8, 10, 12, 14, 16] 
    snr = [-20.0, -10.0, 10.0, 30.0]
    costs = [1]
    
    for ant in tqdm(antennas):
        for cost in costs:
            for seed in seeds:
                if args.pruned:
                    run.use_artifact(f'{args.org}/SemanticAutoEncoder_wn_{ant}_{ant}_aware_20.0_{cost}_pruned/model-seed_{seed}:best', type='model').download()
                else:
                    run.use_artifact(f'{args.org}/SemanticAutoEncoder_wn_{ant}_{ant}_aware_20.0_{cost}/model-seed_{seed}:best', type='model').download()

                find_and_rename_ckpt_files('artifacts', f'aware-{cost}/antennas_{ant}_{ant}/snr_20.0/', str(seed))

            for seed in seeds:
                if args.pruned:
                    run.use_artifact(f'{args.org}/SemanticAutoEncoder_wn_{ant}_{ant}_unaware_None_{cost}_pruned/model-seed_{seed}:best', type='model').download()
                else:
                    run.use_artifact(f'{args.org}/SemanticAutoEncoder_wn_{ant}_{ant}_unaware_None_{cost}/model-seed_{seed}:best', type='model').download()

                find_and_rename_ckpt_files('artifacts', f'unaware-{cost}/antennas_{ant}_{ant}/snr_20.0/', str(seed))

    for s in tqdm(snr):
        for cost in costs:
            for seed in seeds:
                if args.pruned:
                    run.use_artifact(f'{args.org}/SemanticAutoEncoder_wn_8_8_aware_{s}_{cost}_pruned/model-seed_{seed}:best', type='model').download()
                else:
                    run.use_artifact(f'{args.org}/SemanticAutoEncoder_wn_8_8_aware_{s}_{cost}/model-seed_{seed}:best', type='model').download()
            
                find_and_rename_ckpt_files('artifacts', f'aware-{cost}/antennas_8_8/snr_{s}/', str(seed))
            
    wandb.finish()
    
    return None



if __name__ == "__main__":
    main()