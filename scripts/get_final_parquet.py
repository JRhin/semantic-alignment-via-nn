
"""Script for getting the final parquet with the results.
"""
# Add root to the path
import sys
from pathlib import Path
sys.path.append(str(Path(sys.path[0]).parent))

import torch
import polars as pl
from timm import create_model
from pytorch_lightning import Trainer, seed_everything
from torch.utils.data import TensorDataset, DataLoader

from src.linear_optim import LinearOptimizerRE, LinearOptimizerSAE
from src.utils import complex_gaussian_matrix, complex_tensor, snr, prewhiten
from src.models import RelativeEncoder, Classifier, SemanticAutoEncoder
from src.datamodules import DataModule, DataModuleClassifier

def main() -> None:
    """The main loop. 
    """
    import argparse

    description = """
    This python module handles the parquet file generation.

    To check available parameters run 'python /path/to/get_final_parquet.py --help'.
    """
    parser = argparse.ArgumentParser(description=description,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-c',
                        '--checkpoints',
                        help="The checkpoints path. Default 'autoencoders'.",
                        default='autoencoders',
                        type=str)

    parser.add_argument('-n',
                        '--name',
                        help="The parquet file name. Default 'final_results'.",
                        default='final_results',
                        type=str)

    parser.add_argument('-t',
                        '--train',
                        help="Train the linear optimizer. Default True.",
                        default=True,
                        action=argparse.BooleanOptionalAction,
                        type=bool)

    args = parser.parse_args()
    
    # Defining paths
    CURRENT: Path = Path('.')
    DATA_DIR: Path = CURRENT / "data"
    MODELS_DIR: Path = CURRENT / "models"

    batch_size = 512
    trainer = Trainer(inference_mode=True, enable_progress_bar=False, logger=False)
    
    try:
        results = pl.read_parquet(f'{args.name}.parquet')
    except:
        results = pl.DataFrame(schema=[
                                   ('Dataset', pl.String),
                                   ('Encoder', pl.String),
                                   ('Decoder', pl.String),
                                   ('Case', pl.String),
                                   ('Transmitting Antennas', pl.Int64),
                                   ('Receiving Antennas', pl.Int64),
                                   ('Awareness', pl.String),
                                   # ('Target', pl.String),
                                   ('Anchors', pl.Int64),
                                   ('Sigma', pl.Float64),
                                   ('Seed', pl.Int64),
                                   ('Cost', pl.Int64),
                                   ('Alignment Loss', pl.Float64),
                                   ('Classifier Loss', pl.Float64),
                                   ('Accuracy', pl.Float64),
                                   ('SNR', pl.Float64)
                               ])
    # ==============================================================================
    #                      Get results for the SAE absolute
    # ==============================================================================
    # target = 'abs'
    # for autoencoder_path in (MODELS_DIR / f'{args.checkpoints}/{target}').rglob('*.ckpt'):
    for autoencoder_path in (MODELS_DIR / f'{args.checkpoints}/').rglob('*.ckpt'):
        print()
        print()
        print('#'*100)
        print(autoencoder_path)
        # Getting the settings
        _, _, dataset, encoder, decoder, awareness, antennas, sigma, seed = str(autoencoder_path.as_posix()).split('/')
        transmitter, receiver = list(map(int, antennas.split('_')[-2:]))
        # case = case.split('_')[-1]
        sigma = float(sigma.split('_')[-1])
        seed = int(seed.split('.')[0].split('_')[-1])

        if not results.filter((pl.col('Transmitting Antennas')==transmitter)&(pl.col('Receiving Antennas')==receiver)&(pl.col('Seed')==seed)&(pl.col('Sigma')==sigma)&(pl.col('Awareness')==awareness)).is_empty():
            continue
        
        # Setting the seed
        seed_everything(seed, workers=True)

        # Get the channel matrix and white noise sigma
        channel_matrix = complex_gaussian_matrix(mean=0, std=1, size=(receiver, transmitter))

        # Get and setup the datamodule
        datamodule = DataModule(dataset=dataset,
                                encoder=encoder,
                                decoder=decoder,
                                # num_anchors=None,
                                # case=case,
                                # target=target,
                                batch_size=batch_size)
        datamodule.prepare_data()
        datamodule.setup()
                
        # =========================================================================
        #                            Classfier Stuff
        # =========================================================================
        # Define the path towards the classifier
        # clf_path: Path = MODELS_DIR / f"classifiers/{target}/{dataset}/{decoder}/seed_{seed}.ckpt"
        clf_path: Path = MODELS_DIR / f"classifiers/{dataset}/{decoder}/seed_{seed}.ckpt"

        # Load the classifier model
        clf = Classifier.load_from_checkpoint(clf_path)
        clf.eval()

        # Get and setup the classifier datamodule
        clf_datamodule = DataModuleClassifier(dataset=dataset,
                                              decoder=decoder,
                                              # num_anchors=None,
                                              # case=target,
                                              batch_size=batch_size)
        clf_datamodule.prepare_data()
        clf_datamodule.setup()

        # =========================================================================
        #                             Non Linear
        # =========================================================================
        model = SemanticAutoEncoder.load_from_checkpoint(autoencoder_path)
        model.eval()

        cost = model.hparams['cost']

        if awareness == 'unaware':
            model.hparams['channel_matrix'] = channel_matrix
            model.hparams['sigma'] = sigma
        
        # Get the absolute representation in the decoder space
        z_psi_hat = torch.cat(trainer.predict(model=model, datamodule=datamodule))
        
        alignment_metrics = trainer.test(model=model, datamodule=datamodule)[0]
      
        # Get the predictions using as input the z_psi_hat
        dataloader = DataLoader(TensorDataset(z_psi_hat, datamodule.test_data.labels), batch_size=batch_size)
        clf_metrics = trainer.test(model=clf, dataloaders=dataloader)[0]

        results.vstack(pl.DataFrame(
                       {
                           'Dataset': dataset,
                           'Encoder': encoder,
                           'Decoder': decoder,
                           'Case': f'Neural Semantic Precoding/Decoding - Channel {awareness.capitalize()}',
                           'Transmitting Antennas': transmitter,
                           'Receiving Antennas': receiver,
                           'Awareness': awareness,
                           # 'Target': target,
                           'Anchors': None,
                           'Sigma': sigma,
                           'Seed': seed,
                           'Cost': cost,
                           'Alignment Loss': alignment_metrics['test/loss_epoch'],
                           'Classifier Loss': clf_metrics['test/loss_epoch'],
                           'Accuracy': clf_metrics['test/acc_epoch'],
                           'SNR': snr(signal=datamodule.test_data.z_decoder, sigma=sigma)
                       }),
                       in_place=True)


        # =========================================================================
        #                             Linear Optimizer
        # =========================================================================
        # Set awareness
        if awareness == 'aware':
            ch_matrix = channel_matrix
            white_noise_cov = (sigma/2) * torch.view_as_complex(torch.stack((torch.eye(receiver), torch.eye(receiver)), dim=-1))
        elif awareness == 'unaware':
            ch_matrix = torch.view_as_complex(torch.stack((torch.eye(receiver), torch.eye(receiver)), dim=-1))
            white_noise_cov = 0*torch.view_as_complex(torch.stack((torch.eye(receiver), torch.eye(receiver)), dim=-1))
        else:
            raise Exception(f'Wrong awareness passed: {awareness}')
                
        # Get the optimizer
        opt = LinearOptimizerSAE(input_dim=datamodule.input_size,
                                 output_dim=datamodule.output_size,
                                 channel_matrix=ch_matrix,
                                 white_noise_cov=white_noise_cov,
                                 sigma=sigma,
                                 cost=cost)

        # Check if the matrices F and G are pretrained
        if args.train:
            # Fit the linear optimizer
            opt.fit(input=prewhiten(datamodule.train_data.z[:1000]),
                    output=datamodule.train_data.z_decoder[:1000],
                    iterations=15,
                    method='admm')
            test_input = prewithen(datamodule.test_data.z)
        else:
            import scipy.io

            if awareness == 'aware':
                matrices = scipy.io.loadmat(str(autoencoder_path.parent / f'seed_{seed}.mat'))
            else:
                matrices = scipy.io.loadmat(str(autoencoder_path.parent / f'no_seed.mat'))

            prewhiten_data = scipy.io.loadmat(str(MODELS_DIR / f'{args.checkpoints}/{dataset}/prewhiten.mat'))

            # Get the pretrained matrices
            opt.F = torch.tensor(matrices['F'], dtype=torch.complex64)
            opt.G = torch.tensor(matrices['G'], dtype=torch.complex64)
            test_input = torch.tensor(prewhiten_data['test_input'], dtype=datamodule.test_data.z.dtype).T
            test_input = datamodule.test_data.z

        # Set the channel matrix and white noise
        opt.channel_matrix = channel_matrix
        opt.white_noise_cov = (sigma/2) * torch.view_as_complex(torch.stack((torch.eye(receiver), torch.eye(receiver)), dim=-1))

        # Get the z_psi_hat
        z_psi_hat = opt.transform(test_input)

        # Get the predictions using as input the z_psi_hat
        dataloader = DataLoader(TensorDataset(z_psi_hat, datamodule.test_data.labels), batch_size=batch_size)
        clf_metrics = trainer.test(model=clf, dataloaders=dataloader)[0]

        results.vstack(pl.DataFrame(
                       {
                           'Dataset': dataset,
                           'Encoder': encoder,
                           'Decoder': decoder,
                           'Case': f'Linear Semantic Precoding/Decoding - Channel {awareness.capitalize()}',
                           'Transmitting Antennas': transmitter,
                           'Receiving Antennas': receiver,
                           'Awareness': awareness,
                           # 'Target': target,
                           'Anchors': None,
                           'Sigma': sigma,
                           'Seed': seed,
                           'Cost': cost,
                           'Alignment Loss': opt.eval(datamodule.test_data.z, datamodule.test_data.z_decoder),
                           'Classifier Loss': clf_metrics['test/loss_epoch'],
                           'Accuracy': clf_metrics['test/acc_epoch'],
                           'SNR': snr(signal=datamodule.test_data.z_decoder, sigma=sigma)
                       }),
                       in_place=True)

        results = results.with_columns(pl.col('Anchors').cast(pl.Int64))
        results.write_parquet(f'{args.name}.parquet')
    print(results)
    
    return None
    

if __name__ == "__main__":
    main()
