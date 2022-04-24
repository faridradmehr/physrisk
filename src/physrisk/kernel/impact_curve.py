from typing import List, Union

import numpy as np


class Distribution:
    def __init__(self, mean, std_dev):
        self.mean = mean
        self.std_dev = std_dev


class ImpactCurve:
    """Provides the impact on an asset, an impact being either a fractional damage or disruption,
    that occurs as a result of a hazard event of a given intensity."""

    __slots__ = ["intensities", "impact_cdfs"]

    def __init__(
        self,
        intensities: Union[List[float], np.ndarray],
        impact_cdfs=None,
    ):
        """Create a new asset event distribution.
        Args:
            intensities: possible intensities of hazard event.
            impacts: fractional damage or fractional average disruption occurring as a result
                of hazard event of given intensity.
            distributions: provides the pdf and optiononally cdf of the impact distribution
        """

        # probabilities must be sorted and decreasing
        # values must be sorted and non-decreasing (intens[i + 1] >= intens[i])

        if not np.all(np.diff(intensities) > 0):
            raise ValueError("intensities must be sorted and increasing")

        self.intensities = np.array(intensities)
        self.impact_cdfs = impact_cdfs

    def to_prob_matrix(self, impact_bin_edges):
        # construct a cdf probability matrix at each intensity point
        # the probability is the prob that the impact is greater than the specified
        cdf_matrix = np.empty([len(self.intensities), len(impact_bin_edges)])

        for i, _ in enumerate(self.intensities):
            cdf_matrix[i, :] = self.impact_cdfs[i](impact_bin_edges)  # type: ignore

        prob_matrix = cdf_matrix[:, 1:] - cdf_matrix[:, :-1]

        return prob_matrix