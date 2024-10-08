"""In this module there are defined usefull methods:

- complex_gaussian_matrix:
    A method that returns a complex gaussian matrix in the torch.Tensor format.
"""

import torch


# ================================================================
#
#                        Methods Definition 
#
# ================================================================

def complex_compressed_tensor(x: torch.Tensor) -> torch.Tensor:
    """The function compress the feature dimension of the tensor by converting
    half as real part and the other half as imaginary part.

    Args:
        x : torch.Tensor
            The input tensor to compress.

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

    return torch.view_as_complex(x)


def decompress_complex_tensor(x: torch.Tensor) -> torch.Tensor:
    """The function decompress the complex compressed tensor in the original real domain.

    Args:
        x : torch.Tensor
            The input compressed tensor.

    Returns:
        torch.Tensor
            The output decompressed tensor.
    """
    # Split the complex tensor into real and imaginary parts
    real_part = x.real
    imaginary_part = x.imag

    # Concatenate the real and imaginary parts along the feature dimension
    x = torch.cat((real_part, imaginary_part), dim=1)

    return x


def complex_tensor(x: torch.Tensor) -> torch.Tensor:
    """Get the complex form of a tensor.

    Args:
        x : torch.Tensor
            The original tensor.

    Returns:
        torch.Tensor
            The output tensor, which is the complex form of the original tensor.
    """
    device = x.device
    x = torch.stack((x, torch.zeros(x.shape).to(device)), dim=-1)
    return torch.view_as_complex(x)


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


def snr(signal: torch.Tensor,
        sigma: float) -> float:
    """Return the Signal to Noise Ratio.

    Args:
        signal : torch.Tensor
            The signal vector.
        sigma : float
            The sigma squared of the noise.

    Return:
        float
            The Signal to Noise Ratio.
    """
    return 10*torch.log10(torch.mean(signal**2)/sigma**2).item()
    
    

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
    d = 4
    x = torch.randn(n, d)
    # n = torch.normal(mean, std, size=x.shape)
    
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

    
    return None


if __name__ == "__main__":
    main()
