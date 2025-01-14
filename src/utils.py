"""In this module there are defined usefull methods:

- complex_gaussian_matrix:
    A method that returns a complex gaussian matrix in the torch.Tensor format.
"""

import torch
import math


# ================================================================
#
#                        Methods Definition 
#
# ================================================================

def complex_compressed_tensor(x: torch.Tensor,
                              device: str = "cpu") -> torch.Tensor:
    """The function compress the feature dimension of the tensor by converting
    half as real part and the other half as imaginary part.

    Args:
        x : torch.Tensor
            The input tensor to compress.
        device : str
            The device of the tensor. Default cpu.

    Returns:
        torch.Tensor
            The output tensor in complex format.
    """
    n, d = x.shape
    
    if d % 2 != 0:
        x = torch.cat((x, torch.zeros((n, 1), dtype=x.dtype, device=x.device)), dim=1)
        d += 1   # Split the tensor into real and imaginary parts
        
    real_part = x[:, :d//2]
    imaginary_part = x[:, d//2:]

    # Combine real and imaginary parts into a complex tensor
    x = torch.stack((real_part, imaginary_part), dim=-1)

    return torch.view_as_complex(x).to(device)


def decompress_complex_tensor(x: torch.Tensor,
                              device: str = "cpu") -> torch.Tensor:
    """The function decompress the complex compressed tensor in the original real domain.

    Args:
        x : torch.Tensor
            The input compressed tensor.
        device : str
            The device of the tensor. Default cpu.

    Returns:
        torch.Tensor
            The output decompressed tensor.
    """
    # Split the complex tensor into real and imaginary parts
    real_part = x.real
    imaginary_part = x.imag

    # Concatenate the real and imaginary parts along the feature dimension
    x = torch.cat((real_part, imaginary_part), dim=1)

    return x.to(device)


def complex_tensor(x: torch.Tensor,
                   device: str = "cpu") -> torch.Tensor:
    """Get the complex form of a tensor.

    Args:
        x : torch.Tensor
            The original tensor.
        device : str
            The device of the tensor. Default cpu.

    Returns:
        torch.Tensor
            The output tensor, which is the complex form of the original tensor.
    """
    device = x.device
    x = torch.stack((x, torch.zeros(x.shape).to(device)), dim=-1)
    return torch.view_as_complex(x).to(device)


def complex_gaussian_matrix(mean: float,
                            std: float,
                            size: tuple[int]) -> torch.Tensor:
    """A method that returns a complex gaussian matrix in the torch.Tensor format.

    Args:
        mean : float
            The mean of the distribution.
        std : float
            The std of the distribution.
        size : tuple[int]
            The size of the matrix.

    Returns:
        torch.Tensor
            The complex gaussian matrix in the torch.Tensor format.
    """
    # Get the real and imaginary parts
    real_part = torch.normal(mean, std/2, size=size)
    imag_part = torch.normal(mean, std/2, size=size)

    # Stack real and imaginary parts along the last dimensioni
    complex_matrix = torch.stack((real_part, imag_part), dim=-1)

    return torch.view_as_complex(complex_matrix)


def awgn(sigma: float,
         size: torch.Size,
         device: str = "cpu") -> torch.Tensor:
    """A function that returns a noise vector sampled by a complex gaussian of a specified sigma.

    Args:
        sigma : float
            The sigma (std) of a REAL awgn.
        size : torch.Size
            The size of the noise vector.
        device : str
            The device of the tensor. Default cpu.

    Returns:
        torch.Tensor
            The sempled noise vector.
    """
    # Get the complex sigma
    sigma = sigma / math.sqrt(2)
    
    # Get the real and imaginary parts
    r = torch.normal(mean=0, std=sigma, size=size)
    i = torch.normal(mean=0, std=sigma, size=size)
    
    return torch.view_as_complex(torch.stack((r, i), dim=-1)).to(device)


def snr(signal: torch.Tensor,
        sigma: float) -> float:
    """Return the Signal to Noise Ratio.

    Args:
        signal : torch.Tensor
            The signal vector.
        sigma : float
            The sigma of the noise.

    Return:
        float
            The Signal to Noise Ratio.
    """
    return 10*torch.log10(torch.mean(torch.abs(signal)**2)/sigma**2).item()


def sigma_given_snr(snr: float,
                    signal: torch.Tensor) -> float:
    """Given a fixed value of SNR and signal, retrieve the correspoding value of sigma.

    Args:
        snr : float
            The Signal to Noise Ration in dB.
        signal : torch.Tensor
            The number of receiving antennas.
        cost : float
            The cost for the transmitter.

    Returns:
        float
            The corresponding sigma given snr and a signal.
    """
    snr_no_db = math.pow(10, snr/10)
    signal_power = torch.mean(torch.abs(signal)**2)
    return math.sqrt(signal_power/snr_no_db)


def prewhiten(x_train: torch.Tensor,
              x_test: torch.Tensor = None,
              device: str = "cpu") -> tuple[torch.Tensor, torch.Tensor, torch.Tensor] | tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Prewhiten the training and test data using only training data statistics.
    
    Args:
        x_train : torch.Tensor
            The training torch.Tensor matrix.
        x_test : torch.Tensor
            The testing torch.Tensor matrix. Default None.
        device : str
            The device of the tensor. Default cpu.
            
    Returns:
        z_train : torch.Tensor
            Prewhitened training matrix.

        L : torch.Tensor
            The matrix resulting from the Cholesky decomposition.

        mean : torch.Tensor
            The mean of the x_train input.
        
        z_test : torch.Tensor
            Prewhitened test matrix.
    """
    # --- Prewhiten the training set ---
    C = torch.cov(x_train)  # Training set covariance
    L, _ = torch.linalg.cholesky_ex(C)  # Cholesky decomposition C = LL^H
    mean = x_train.mean(axis=1)[:, None]
    z_train = x_train - mean # Center the training set
    z_train = torch.linalg.solve(L, z_train)  # Prewhitened training set

    if x_test is not None:
        z_test = x_test - mean  # Center the test set
        z_test = torch.linalg.solve(L, x_test)  # Prewhitened training set
        return z_train.to(device), L.to(device), mean.to(device), z_test.to(device)
    
    return z_train.to(device), L.to(device), mean.to(device)

# ================================================================
#
#                        Main Definition 
#
# ================================================================

def main() -> None:
    """Some quality tests...
    """
    
    # Variable definition
    mean: float = 0.
    std: float = 1.
    size: tuple[int] = (4, 4)

    n = 10
    d = 20
    x = torch.randn(n, d)
    
    print("Performing first test...", end="\t")
    complex_matrix = complex_gaussian_matrix(mean=mean, std=std, size=size)
    print("[PASSED]")

    print()
    print("Performing second test...", end="\t")
    complex_tensor(x)
    print("[PASSED]")

    print()
    print("Performing third test...", end='\t')
    sn_ratio = snr(x.real, std)
    print("[PASSED]")
    
    print()
    print("Performing fourth test...", end='\t')
    x_c = complex_compressed_tensor(x)
    print("[PASSED]")

    print()
    print("Performing fifth test...", end='\t')
    x_hat = decompress_complex_tensor(x_c)

    if not torch.all(torch.eq(x_hat[:, :d], x)):
        raise Exception("The compression and decompression are not working as intended")
    
    print("[PASSED]")
    
    print()
    print("Performing sixth test...", end="\t")
    prewhiten(x)
    print("[PASSED]")

    print()
    print("Performing seventh test...", end="\t")
    sigma = sigma_given_snr(snr=10, signal=x)
    assert sigma > 0, "[Error]: sigma is not positive."
    print("[PASSED]")

    print()
    print("Performing eight test...", end="\t")
    awgn(sigma=sigma, size=x.shape)
    print("[PASSED]")

    
    return None


if __name__ == "__main__":
    main()
