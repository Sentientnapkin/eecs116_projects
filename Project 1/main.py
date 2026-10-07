"""Run either part of the localization exercise."""

import argparse

import matplotlib.pyplot as plt

from filter import noise_covariances, run_filter
from support import load_dataset, plot_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", type=int, choices=(1, 2), required=True)
    parser.add_argument("--dataset", type=int, choices=(1, 4, 9), required=True)
    args = parser.parse_args()
    process_noise, measurement_noise = noise_covariances(args.part)
    result = run_filter(
        load_dataset(args.dataset), process_noise, measurement_noise, part=args.part
    )
    plot_result(result)
    plt.show()
