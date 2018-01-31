"""Provide results class for IDTxl network analysis.

Created on Wed Sep 20 18:37:27 2017

@author: patricia
"""
import copy as cp
import itertools as it
import numpy as np
from . import idtxl_utils as utils
from . import idtxl_exceptions as ex
try:
    import networkx as nx
except ImportError as err:
    ex.package_missing(
        err,
        ('networkx is not available on this system. Install it from '
         'https://pypi.python.org/pypi/networkx/2.0 to export and plot IDTxl '
         'results in this format.'))


class DotDict(dict):
    """Dictionary with dot-notation access to values.

    Provides the same functionality as a regular dict, but also allows
    accessing values using dot-notation.

    Example:

        >>> from idtxl.results import DotDict
        >>> d = DotDict({'a': 1, 'b': 2})
        >>> d.a
        >>> # Out: 1
        >>> d['a']
        >>> # Out: 1
    """
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __dir__(self):
        """Return dictionary keys as list of attributes."""
        return self.keys()

    def __deepcopy__(self, memo):
        """Provide deep copy capabilities.

        Following a fix described here:
        https://github.com/aparo/pyes/pull/115/commits/d2076b385c38d6d00cebfe0df7b0d1ba8df934bc
        """
        dot_dict_copy = DotDict([
            (cp.deepcopy(k, memo),
             cp.deepcopy(v, memo)) for k, v in self.items()])
        return dot_dict_copy

    def __getstate__(self):
        # For pickling the object
        return self

    def __setstate__(self, state):
        # For un-pickling the object
        self.update(state)
        self.__dict__ = self


class Results():
    """Parent class for results of network analysis algorithms.

    Provide a container for results of network analysis algorithms, e.g.,
    MultivariateTE or ActiveInformationStorage.

    Attributes:
        settings : dict
            settings used for estimation of information theoretic measures and
            statistical testing
        data : dict
            data properties, contains

                - n_nodes : int - total number of nodes in the network
                - n_realisations : int - number of samples available for
                  analysis given the settings (e.g., a high maximum lag used in
                  network inference, results in fewer data points available for
                  estimation)
                - normalised : bool - indicates if data were normalised before
                  estimation
                - single
    """

    def __init__(self, n_nodes, n_realisations, normalised):
        self.settings = DotDict({})
        self.data = DotDict({
            'n_nodes': n_nodes,
            'n_realisations': n_realisations,
            'normalised': normalised
        })


class ResultsNetworkInference(Results):
    """Store results of network inference.

    Provide a container for results of network inference algorithms, e.g.,
    MultivariateTE or Bivariate TE.

    Note that for convenience all dictionaries in this class can additionally
    be accessed using dot-notation: res_network.single_target[2].omnibus_pval
    or res_network.single_target[2].['omnibus_pval'].

    Attributes:
        settings : dict
            settings used for estimation of information theoretic measures and
            statistical testing
        data : dict
            data properties, contains

                - n_nodes : int - total number of nodes in the network
                - n_realisations : int - number of samples available for
                  analysis given the settings (e.g., a high maximum lag used in
                  network inference, results in fewer data points available for
                  estimation)
                - normalised : bool - indicates if data were normalised before
                  estimation
                - single
        adjacency_matrix : 2D numpy array
            adjacency matrix describing the inferred network structure, if
            applicable entries denote the information-transfer delay
        single_target : dict
            results for individual targets, contains for each target

                - omnibus_te : float - TE-value for joint information transfer
                  from all sources into the target
                - omnibus_pval : float - p-value of omnibus information
                  transfer into the target
                - omnibus_sign : bool - significance of omnibus information
                  transfer wrt. to the alpha_omnibus specified in the settings
                - selected_vars_full : list of tuples - variables with
                  significant information about the current value of the
                  target, a variable is described by the index of the process
                  in the data and its lag in samples
                - selected_vars_sources : list of tuples - source variables
                  with significant information about the current value
                - selected_vars_target : list of tuples - target variables
                  with significant information about the current value
                - selected_sources_pval : array of floats - p-value for each
                  selected variable
                - selected_sources_te : array of floats - TE-value for each
                  selected variable
                - sources_tested : list of int - list of sources tested for the
                  current target
                - current_value : tuple - current value used for analysis,
                  described by target and sample index in the data

        targets_analysed : list
            list of targets analyzed
        fdr_correction : dict
            FDR-corrected results, see documentation of network inference
            algorithms and stats.network_fdr

    """

    def __init__(self, n_nodes, n_realisations, normalised):
        super().__init__(n_nodes, n_realisations, normalised)
        self.adjacency_matrix = np.zeros(
            (self.data.n_nodes, self.data.n_nodes), dtype=int)
        self.single_target = {}
        self.targets_analysed = []
        self._add_fdr(None)

    def _add_single_target(self, target, results, settings):
        """Add analysis result for a single target."""
        # Check if new target is part of the network
        if target > (self.data.n_nodes - 1):
            raise RuntimeError('Can not add single target results - target '
                               'index {0} larger than no. nodes ({1}).'.format(
                                   target, self.data.n_nodes))
        # Don't add duplicate targets
        if self._duplicate_targets(target):
            raise RuntimeError('Can not add single target results - results '
                               'for target {0} already exist.'.format(target))
        # Dont' add results with conflicting settings
        if utils.conflicting_entries(self.settings, settings):
            raise RuntimeError('Can not add single target results - analyses '
                               'settings are not equal.')
        # Add results
        self.settings.update(DotDict(settings))
        self.single_target[target] = DotDict(results)
        self.targets_analysed = list(self.single_target.keys())
        self._update_adjacency_matrix(target=target)

    def combine_results(self, *results):
        """Combine multiple (partial) results objects.

        Combine a list of partial network inference results into a single
        results object (e.g., results from analysis parallelized over target
        nodes). Raise an error if duplicate targets occur in partial results,
        or if analysis settings are not equal.

        Note that only conflicting settings cause an error (i.e., settings with
        equal keys but different values). If additional settings are included
        in partial results (i.e., settings with different keys) these settings
        are added to the common settings dictionary.

        Remove FDR-corrections from partial results before combining them. FDR-
        correction performed on the basis of parts of the network a not valid
        for the combined network.

        Args:
            results : list of Results objects
                network inference results from .analyse_network methods,
                where each dict entry represents partial results for one or
                multiple target nodes

        Returns:
            dict
                combined results dict
        """
        for r in results:
            targets = r.targets_analysed
            if utils.conflicting_entries(self.settings, r.settings):
                raise RuntimeError('Can not combine results - analyses '
                                   'settings are not equal.')
            for t in targets:
                # Remove potential partial FDR-corrected results. These are no
                # longer valid for the combined network.
                if self._duplicate_targets(t):
                    raise RuntimeError('Can not combine results - results for '
                                       'target {0} already exist.'.format(t))
                try:
                    del r.fdr_corrected
                    print('Removing FDR-corrected results.')
                except AttributeError:
                    pass
                self._add_single_target(t, r.single_target[t], r.settings)

    def get_target_sources(self, target, fdr=False):
        """Return list of sources for given target.

        Args:
            target : int
                target index
            fdr : bool [optional]
                if True, sources are returned for FDR-corrected results
        """
        if target not in self.targets_analysed:
            raise RuntimeError('No results for target {0}.'.format(target))
        if fdr:
            try:
                return np.unique(np.array(
                    [s[0] for s in (self.fdr_correction[target].
                                    selected_vars_sources)]))
            except AttributeError:
                raise RuntimeError('No FDR-corrected results have been added.')
            except KeyError:
                RuntimeError(
                    'Didn''t find results for target {0}.'.format(target))
        else:
            try:
                return np.unique(np.array(
                    [s[0] for s in (self.single_target[target].
                                    selected_vars_sources)]))
            except AttributeError:
                raise RuntimeError('No results have been added.')
            except KeyError:
                raise RuntimeError(
                    'Didn''t find results for target {0}.'.format(target))

    def get_target_delays(self, target, find_delay='max_te', fdr=False):
        """Return list of information-transfer delays for given target.

        Return a list of information-transfer delays for given target.
        Information-transfer delays are determined by the lag of the variable
        in a sources' past that has the highest information transfer into the
        target process. There are two ways of idendifying the variable with
        maximum information transfer:

            a) use the variable with the highest absolute TE value (highest
               information transfer),
            b) use the variable with the smallest p-value (highest statistical
               significance).

        Args:
            target : int
                target index
            fdr : bool [optional]
                print FDR-corrected results (default=False)
            find_delay : str [optional]
                use maximum TE value ('max_te') or p-value ('max_p') to
                determine the source-target delay (default='max_te')

        Returns:
            numpy array
                Information-transfer delays for each source
        """
        sources = self.get_target_sources(target, fdr)
        delays = np.zeros(sources.shape[0]).astype(int)

        # Get the source index for each past source variable of the target
        all_vars_sources = np.array(
            [x[0] for x in
             self.single_target[target].selected_vars_sources])
        # Get the lag for each past source variable of the target
        all_vars_lags = np.array(
            [x[1] for x in self.single_target[target].selected_vars_sources])
        # Get p-values and TE-values for past source variable
        pval = self.single_target[target].selected_sources_pval
        te = self.single_target[target].selected_sources_te

        # Find delay for each source
        for (ind, s) in enumerate(sources):
            if find_delay == 'max_p':
                # Find the minimum p-value amongst the variables in source s
                delays_ind = np.argmin(pval[all_vars_sources == s])
            elif find_delay == 'max_te':
                # Find the maximum TE-value amongst the variables in source s
                delays_ind = np.argmax(te[all_vars_sources == s])

            delays[ind] = all_vars_lags[all_vars_sources == s][delays_ind]

        return delays

    def export_networkx_graph(self, fdr=False):
        """Generate networkx graph object for an inferred network.

        Generate a weighted, directed graph object from the network of inferred
        (multivariate) interactions (e.g., multivariate TE), using the networkx
        class for directed graphs (DiGraph). The graph is weighted by the
        reconstructed source-target delays (see documentation for method
        get_target_delays for details).

        Args:
            fdr : bool [optional]
                return FDR-corrected results

        Returns:
            DiGraph object
                instance of a directed graph class from the networkx
                package (DiGraph)
        """
        if fdr:
            return nx.from_numpy_matrix(self.fdr_correction.adjacency_matrix,
                                        create_using=nx.DiGraph())
        else:
            return nx.from_numpy_matrix(self.adjacency_matrix,
                                        create_using=nx.DiGraph())

    def export_networkx_source_graph(self, target,
                                     sign_sources=True, fdr=False):
        """Generate graph object of source variables for a single target.

        Generate a graph object from the network of (multivariate)
        interactions (e.g., multivariate TE) between single source variables
        and a target process using the networkx class for directed graphs
        (DiGraph). The graph shows the information transfer between individual
        source variables and the target.

        Args:
            target : int
                target index
            sign_sources : bool [optional]
                add only sources significant information contribution
                (default=True)
            fdr : bool [optional]
                return FDR-corrected results

        Returns:
            DiGraph object
                instance of a directed graph class from the networkx
                package (DiGraph)
        """
        if target not in self.targets_analysed:
            raise RuntimeError('No results for target {0}.'.format(target))
        graph = nx.DiGraph()
        # Add the target as a node. Each node is a tuple with format (process
        # index, sample index).
        graph.add_node(self.single_target[target].current_value)

        if sign_sources:
            # Add only significant past variables as nodes.
            if fdr:
                graph.add_nodes_from(
                    (self.fdr_correction.single_target[target].
                     selected_vars_full[:]))
            else:
                graph.add_nodes_from(
                    self.single_target[target].selected_vars_full[:])
        else:
            # Add all tested past variables as nodes.
            # Get all sample indices.
            current_value = self.single_target[target].current_value
            min_lag = self.settings.min_lag_sources
            max_lag = self.settings.max_lag_sources
            tau = self.settings.max_lag_sources
            samples_tested = np.arange(
                current_value[1] - min_lag, current_value[1] - max_lag, -tau)
            # Get source indices
            sources_tested = self.single_target[target].sources_tested
            # Create tuples from source and sample indices
            nodes = [i for i in it.product(sources_tested, samples_tested)]
            graph.add_nodes_from(nodes)

        # Add edges from significant past variables to the target. Here, one
        # could add additional info in the future, networkx graphs support
        # attributes for graphs, nodes, and edges.
        if fdr:
            for v in range(len(self.single_target[target].selected_vars_full)):
                graph.add_edge(
                    (self.fdr_correction.single_target[target].
                     selected_vars_full[v]),
                    target)
        else:
            for v in range(len(self.single_target[target].selected_vars_full)):
                graph.add_edge(
                    self.single_target[target].selected_vars_full[v],
                    self.single_target[target].current_value)
        if self.settings['verbose']:
            print(graph.node)
            print(graph.edge)
            graph.number_of_edges()
        return graph

    def print_to_console(self, fdr=False):
        """Print results of network inference to console.

        Print results of network inference to console. Output looks like this:

            0 -> 1, u = 2
            0 -> 2, u = 3
            0 -> 3, u = 2
            3 -> 4, u = 1
            4 -> 3, u = 1

        indicating significant information transfer source -> target with an
        information-transfer delay u (see documentation for method
        get_target_delays for details). The network can either be plotted from
        FDR-corrected results or uncorrected results.

        Args:
            fdr : bool [optional]
                print FDR-corrected results (default=False)
        """
        if fdr:
            adjacency_matrix = self.fdr_correction.adjacency_matrix
        else:
            adjacency_matrix = self.adjacency_matrix
        link_found = False
        for s in range(self.data.n_nodes):
            for t in range(self.data.n_nodes):
                if adjacency_matrix[s, t]:
                    print('\t{0} -> {1}, u: {2}'.format(
                        s, t, adjacency_matrix[s, t]))
                    link_found = True
        if not link_found:
            print('No significant links in network.')

    def _duplicate_targets(self, target):
        # Test if target is already present in object
        if target in self.targets_analysed:
            return True
        else:
            return False

    def _update_adjacency_matrix(self, target=None, fdr=False):
        """Update adjacency matrix."""
        # If no target is given, build adjacency matrix from scratch, else:
        # just update the requested target to save time.
        if target is None:
            update_targets = self.targets_analysed
        else:
            update_targets = [target]

        for t in update_targets:
            sources = self.get_target_sources(target=t, fdr=fdr)
            delays = self.get_target_delays(target=t, fdr=fdr)
            if sources.size:
                if fdr:
                    self.fdr_correction.adjacency_matrix[sources, t] = delays
                else:
                    self.adjacency_matrix[sources, t] = delays

    def _add_fdr(self, fdr):
        # Add results of FDR-correction
        if fdr is None:
            self.fdr_correction = DotDict()
        else:
            self.fdr_correction = DotDict(fdr)
            self.fdr_correction.adjacency_matrix = np.zeros(
                (self.data.n_nodes, self.data.n_nodes), dtype=int)
            self._update_adjacency_matrix(fdr=True)
