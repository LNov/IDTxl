# -*- coding: utf-8 -*-
"""
Created on Mon Mar  7 18:13:27 2016

@author: patricia
"""
import sys
import copy as cp
import numpy as np
import utils

VERBOSE = True


def omnibus_test(analysis_setup, data, n_permutations=3):
    """Perform an omnibus test on identified conditional variables.

    Test the joint information transfer from all identified sources to the
    current value conditional on candidates in the target's past. To test for
    significance, this is repeated for shuffled realisations of the sources.
    The distribution of values from shuffled data is then used as test
    distribution.

    Args:
        analysis_setup: instance of Multivariate_te class
        data: instance of Data class
        n_permutations: number of permutations for testing (default=500)

    Returns:
        boolean indicating statistical significance
        the test's p-value
    """
    print('no. target sourcesces: {0}, no. sources: {1}'.format(
                                    len(analysis_setup.conditional_target),
                                    len(analysis_setup.conditional_sources)))

    # Create temporary variables b/c realisations for sources and targets are
    # created on the fly, which is costly (this does not apply to the current
    # value realisations).
    cond_source_realisations = analysis_setup._conditional_sources_realisations
    cond_target_realisations = analysis_setup._conditional_target_realisations
    te_orig = analysis_setup._cmi_estimator.estimate(
                                    cond_source_realisations,
                                    analysis_setup._current_value_realisations,
                                    cond_target_realisations)

    surr_distribution = np.zeros(n_permutations)
    if data.n_replications > 1:     # TODO make this a kwarg
        permute_over_replications = True
    else:
        permute_over_replications = False

    for perm in range(n_permutations):
        if permute_over_replications:
            surr_conditional_realisations = data.permute_data(
                                        analysis_setup.current_value,
                                        analysis_setup.conditional_sources)[0]
        else:
            surr_conditional_realisations = (_permute_realisations(
                                            cond_source_realisations,
                                            analysis_setup._replication_index))
        surr_distribution[perm] = analysis_setup._cmi_estimator.estimate(
                                    surr_conditional_realisations,
                                    analysis_setup._current_value_realisations,
                                    cond_target_realisations)
    [significance, pvalue] = _find_pvalue(te_orig, surr_distribution)
    return significance, pvalue


def max_statistic(analysis_setup, data, candidate_set, te_max_candidate,
                  n_permutations=3):
    """Perform maximum statistics for one candidate source.

    Test if a transfer entropy value is significantly bigger than the maximum
    values obtained from surrogates of all remanining candidates.

    Args:
        analysis_setup: instance of Multivariate_te class
        data: instance of Data class
        candidate_set: list of indices of remaning candidates
        te_max_candidate: transfer entropy value to be tested
        n_permutations: number of permutations for testing (default=500)

    Returns:
        boolean indicating statistical significance
        the test's p-value
    """
    test_set = cp.copy(candidate_set)

    if not test_set:  # TODO this is an interim thing -> decide what to do
        return True

    stats_table = _create_surrogate_table(analysis_setup, data, test_set,
                                          n_permutations)
    max_distribution = _find_table_max(stats_table)
    [significance, pvalue] = _find_pvalue(te_max_candidate, max_distribution)
    # return np.random.rand() > 0.5
    # return True
    return significance, pvalue


def max_statistic_sequential(analysis_setup, data, n_permutations=5):
    """Perform sequential maximum statistics for a set of candidate sources.

    Test if sorted transfer entropy (TE) values are significantly bigger than
    their respective counterpart obtained from surrogates of all remanining
    candidates: test if the biggest TE is bigger than the distribution
    of biggest TE surrogate values; test if the 2nd biggest TE is bigger than
    the distribution of 2nd biggest surrogate TE values; ...
    Stop comparison if a TE value is non significant, all smaller values are
    considered non-significant as well.

    Args:
        analysis_setup: instance of Multivariate_te class
        data: instance of Data class
        n_permutations: number of permutations for testing (default=500)

    Returns:
        boolean indicating statistical significance
        the test's p-value
    """
    conditional_te = np.empty(len(analysis_setup.conditional_full))
    i = 0
    for conditional in analysis_setup.conditional_full:  # TODO only test source candidates
        [temp_cond, temp_cand] = analysis_setup._remove_realisation(
                                            analysis_setup.conditional_full,
                                            conditional)
        conditional_te[i] = analysis_setup._cmi_estimator.estimate(
                                    temp_cand,
                                    analysis_setup._current_value_realisations,
                                    temp_cond)
        i += 1
    conditional_order = np.argsort(conditional_te)
    conditional_te_sorted = conditional_te
    conditional_te_sorted.sort()

    # TODO not sure about this, because the surrogate table also contains the
    # candidate we're testing
    stats_table = _create_surrogate_table(analysis_setup, data,
                                          analysis_setup.conditional_full,
                                          n_permutations)
    max_distribution = _sort_table_max(stats_table)

    significance = np.zeros(len(analysis_setup.conditional_full)).astype(bool)
    pvalue = np.zeros(len(analysis_setup.conditional_full))
    for c in range(len(analysis_setup.conditional_full)):
        [s, v] = _find_pvalue(conditional_te_sorted[c],
                              max_distribution[c, ])
        significance[c] = s
        pvalue[c] = v

        if not s:
            break

    # get back original order
    significance = significance[conditional_order]
    pvalue = pvalue[conditional_order]

    # return True
    return significance, pvalue


def min_statistic(analysis_setup, data, candidate_set, te_min_candidate,
                  n_permutations=3):
    """Perform minimum statistics for one candidate source.

    Test if a transfer entropy value is significantly bigger than the minimum
    values obtained from surrogates of all remanining candidates.

    Args:
        analysis_setup: instance of Multivariate_te class
        data: instance of Data class
        candidate_set: list of indices of remaning candidates
        te_min_candidate: transfer entropy value to be tested
        n_permutations: number of permutations for testing (default=500)

    Returns:
        boolean indicating statistical significance of the test's p-value
        pvalue
    """
    test_set = cp.copy(candidate_set)

    if not test_set:  # TODO this is an interim thing -> decide what to do
        return True

    stats_table = _create_surrogate_table(analysis_setup, data, test_set,
                                          n_permutations)
    min_distribution = _find_table_min(stats_table)
    [significance, pvalue] = _find_pvalue(te_min_candidate, min_distribution)
    # return np.random.rand() > 0.5
    return significance, pvalue


def _create_surrogate_table(analysis_setup, data, idx_test_set,
                            n_permutations):
    """Create a table of surrogate transfer entropy values.

    Calculate transfer entropy between surrogates for each source in the test
    set and the target in the analysis setup using the current conditional in
    the analysis setup.

    Args:
        analysis_setup: instance of Multivariate_te
        data: instance of Data
        idx_test_set: list od indices indicating samples to be used as sources
        n_permutations: number of permutations per source in test set

    Returns:
        numpy array of te values with dimensions (length test set, number of
        surrogates)
    """
    stats_table = np.zeros((len(idx_test_set), n_permutations))
    current_value_realisations = analysis_setup._current_value_realisations
    idx_c = 0
    if data.n_replications > 1:
        permute_over_replications = True
    else:
        permute_over_replications = False

    if VERBOSE:
        print('create surrogates table')
    for candidate in idx_test_set:
        if VERBOSE:
            print('\tcand. {0}, n_perm: {1}. Done:    '.format(candidate,
                                                               n_permutations),
                  end='')
        for perm in range(n_permutations):
            if permute_over_replications:
                surr_candidate_realisations = data.permute_data(
                                                analysis_setup.current_value,
                                                [candidate])[0]
            else:
                [real, repl_idx] = data.get_realisations(
                                                analysis_setup.current_value,
                                                [candidate])
                surr_candidate_realisations = _permute_realisations(real,
                                                                    repl_idx)
            stats_table[idx_c, perm] = analysis_setup._cmi_estimator.estimate(
                        surr_candidate_realisations,
                        current_value_realisations,
                        analysis_setup._conditional_realisations)  # TODO remove current candidate from this
            if VERBOSE:
                print('\b\b\b{num:03d}'.format(num=perm + 1), end='')
                sys.stdout.flush()
        if VERBOSE:
            print(' ')
        idx_c += 1

    return stats_table


def _find_table_max(table):
    """Find maximum for each column of a table."""
    return np.max(table, axis=0)


def _find_table_min(table):
    """Find minimum for each column of a table."""
    return np.min(table, axis=0)


def _sort_table_max(table):
    """Sort each column in a table in ascending order."""
    for permutation in range(table.shape[1]):
        table[:, permutation].sort()
    return table


def _sort_table_min(table):
    """Sort each column in a table in descending order."""
    table_sorted = np.empty(table.shape)
    for permutation in range(0, table.shape[1]):
        table_sorted[:, permutation] = utils.sort_descending(
                                            table[:, permutation])
    return table_sorted


def _permute_realisations(realisations, replication_idx, perm_range='max'):
    """Permute realisations in time within each replication.

    Permute realisations in time within each replication. This is the fall-back
    option if the number of replications is too small to allow a sufficient
    number of permutations for the generation of surrogate data.

    Args:
        realisations : numpy array
            shape[0] realisations of shape[1] variables
        replication_idx : numpy array
            the index of the replication each realisation came from
        perm_range : int or 'max'
            range in which realisations can be permutet, if 'max' realisations
            are permuted within the whole replication, otherwise blocks of
            length perm_range are permuted one at a time

    Returns:
        numpy array
            realisations permuted over time
    """
    if type(perm_range) is not str:
        assert(perm_range > 2), ('Permutation range has to be larger than 2',
                                 'otherwise there is nothing to permute.')
    realisations_perm = cp.copy(realisations)

    # Build a permuation mask that can be applied to all realisation from one
    # replication at a time.
    n_per_repl = sum(replication_idx == 0)
    if perm_range == 'max':
        perm = np.random.permutation(n_per_repl)
    else:
        perm = np.empty(n_per_repl, dtype=int)
        remainder = n_per_repl % perm_range
        i = 0
        for p in range(0, n_per_repl // perm_range):
            perm[i:i + perm_range] = np.random.permutation(perm_range) + i
            i += perm_range
        if remainder > 0:
            perm[-remainder:] = np.random.permutation(remainder) + i

    # Apply permutation to data.
    for replication in range(max(replication_idx) + 1):
        mask = replication_idx == replication
        d = realisations_perm[mask, :]
        realisations_perm[mask, :] = d[perm, :]

    return realisations_perm


def _find_pvalue(statistic, distribution, alpha=0.05, tail='one'):
    """Find p-value of a test statistic under some distribution.

    Args:
        statistic: value to be tested against distribution
        distribution: 1-dimensional numpy array
        alpha: critical alpha level
        tail: 'one' or 'two' for one-/two-tailed testing

    Returns:
        boolean indicating statistical significance
        the test's p-value
    """
    assert(distribution.ndim == 1)
    if tail == 'one':
        pvalue = sum(distribution > statistic) / distribution.shape[0]
    else:
        p_bigger = sum(distribution > statistic) / distribution.shape[0]
        p_smaller = sum(distribution < statistic) / distribution.shape[0]
        pvalue = min(p_bigger, p_smaller)
    significance = pvalue < alpha
    return significance, pvalue
