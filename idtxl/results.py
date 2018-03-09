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
        # self.__dict__ = self


class Results():
    """Parent class for results of network analysis algorithms.

    Provide a container for results of network analysis algorithms, e.g.,
    MultivariateTE or ActiveInformationStorage.

    Attributes:
        settings : dict
            settings used for estimation of information theoretic measures and
            statistical testing
        data_properties: dict
            data properties, contains

                - n_nodes : int - total number of nodes in the network
                - n_realisations : int - number of samples available for
                  analysis given the settings (e.g., a high maximum lag used in
                  network inference, results in fewer data points available for
                  estimation)
                - normalised : bool - indicates if data were z-standardised
                  before the estimation
    """

    def __init__(self, n_nodes, n_realisations, normalised):
        self.settings = DotDict({})
        self.data_properties = DotDict({
            'n_nodes': n_nodes,
            'n_realisations': n_realisations,
            'normalised': normalised
        })

    def _print_edge_list(self, adjacency_matrix, weights):
        """Print edge list to console."""
        link_found = False
        for s in range(self.data_properties.n_nodes):
            for t in range(self.data_properties.n_nodes):
                if adjacency_matrix[s, t]:
                    link_found = True
                    if weights == 'binary':
                        print('\t{0} -> {1}'.format(
                            s, t, weights, adjacency_matrix[s, t]))
                    else:
                        print('\t{0} -> {1}, {2}: {3}'.format(
                            s, t, weights, adjacency_matrix[s, t]))

        if not link_found:
            print('No significant links found in the network.')

    def _export_to_networkx(self, adjacency_matrix, weights):
        """Create networkx DiGraph object from numpy adjacency matrix."""
        # use 'weights' parameter (string) as networkx edge property name
        # and use adjacency matrix entries as edge property values
        custom_type = [(weights, type(adjacency_matrix[0, 0]))]
        custom_npmatrix = np.matrix(adjacency_matrix, dtype=custom_type)
        return nx.from_numpy_matrix(custom_npmatrix, create_using=nx.DiGraph())

    def _export_brain_net(self, adjacency_matrix, mni_coord, file_name,
                          **kwargs):
        """Export network to BrainNet Viewer.

        Export networks to BrainNet Viewer (project home page:
        http://www.nitrc.org/projects/bnv/). BrainNet Viewer is a MATLAB
        toolbox offering brain network visualisation (e.g., 'glass' brains).
        The function creates text files *.node and *.edge, containing
        information on node location (in MNI coordinates), directed edges, node
        color and size.

        References:

        - Xia, M., Wang, J., & He, Y. (2013). BrainNet Viewer: A Network
          Visualization Tool for Human Brain Connectomics. PLoS ONE 8(7):
          e68910. https://doi.org/10.1371/journal.pone.0068910

        Args:
            adjacency_matrix : 2D numpy array
                adjacency matrix to be exported
            mni_coord : numpy array
                MNI coordinates (x,y,z) of the sources, array with size [n 3],
                where n is the number of nodes
            file_name : str
                file name for output files *.node and *.edge, including the
                path to the file
            labels : array type of str [optional]
                list of node labels of length n, description or label for each
                node. Note that labels can't contain spaces (causes BrainNet to
                crash), the function will remove any spaces from labels
                (default=no labels)
            node_color : array type of colors [optional]
                BrainNet gives you the option to color nodes according to the
                values in this vector (length n), see BrainNet Manual
            node_size : array type of int [optional]
                BrainNet gives you the option to size nodes according to the
                values in this array (length n), see BrainNet Manual
        """
        # Check input and get default settings for plotting. The default for
        # node labels is a list of '-' (no labels).
        n_nodes = adjacency_matrix.shape[0]
        n_edges = np.sum(adjacency_matrix > 0)
        labels = kwargs.get('labels', ['-' for i in range(n_nodes)])
        node_color = kwargs.get('node_color', np.ones(n_nodes))
        node_size = kwargs.get('node_size', np.ones(n_nodes))
        if n_edges == 0:
            Warning('No edges in results file. Nothing to plot.')
        assert adjacency_matrix.shape[0] == adjacency_matrix.shape[1], (
            'Adjacency matrix must be quadratic.')
        assert mni_coord.shape[0] == n_nodes and mni_coord.shape[1] == 3, (
            'MNI coordinates must have shape [n_nodes, 3].')
        assert len(labels) == n_nodes, (
            'Labels must have same length as no. nodes.')
        assert len(node_color) == n_nodes, (
            'Node colors must have same length as no. nodes.')
        assert len(node_size) == n_nodes, (
            'Node size must have same length as no. nodes.')

        # Check, if there are blanks in the labels and delete them, otherwise
        # BrainNet viewer chrashes
        labels_stripped = [l.replace(" ", "") for l in labels]

        # Write node file.
        with open('{0}.node'.format(file_name), 'w') as text_file:
            for n in range(n_nodes):
                print('{0}\t{1}\t{2}\t'.format(*mni_coord[n, :]),
                      file=text_file, end='')
                print('{0}\t{1}\t'.format(node_color[n], node_size[n]),
                      file=text_file, end='')
                print('{0}'.format(labels_stripped[n]), file=text_file)

        # Write edge file.
        with open('{0}.edge'.format(file_name), 'w') as text_file:
            for i in range(n_nodes):
                for j in range(n_nodes):
                    print('{0}\t'.format(adjacency_matrix[i, j]),
                          file=text_file, end='')
                print('', file=text_file)

    def _check_result(self, process, settings):
        # Check if new result process is part of the network
        if process > (self.data_properties.n_nodes - 1):
            raise RuntimeError('Can not add single result - process {0} is not'
                               ' in no. nodes in the data ({1}).'.format(
                                   process, self.data_properties.n_nodes))
        # Don't add duplicate processes
        if self._is_duplicate_process(process):
            raise RuntimeError('Can not add single result - results for target'
                               ' or process {0} already exist.'.format(
                                   process))
        # Don't add results with conflicting settings
        if utils.conflicting_entries(self.settings, settings):
            raise RuntimeError(
                'Can not add single result - analysis settings are not equal.')

    def _is_duplicate_process(self, process):
        # Test if process is already present in object
        if process in self._processes_analysed:
            return True
        else:
            return False

    def combine_results(self, *results):
        """Combine multiple (partial) results objects.

        Combine a list of partial network analysis results into a single
        results object (e.g., results from analysis parallelized over
        processes). Raise an error if duplicate processes occur in partial
        results, or if analysis settings are not equal.

        Note that only conflicting settings cause an error (i.e., settings with
        equal keys but different values). If additional settings are included
        in partial results (i.e., settings with different keys) these settings
        are added to the common settings dictionary.

        Remove FDR-corrections from partial results before combining them. FDR-
        correction performed on the basis of parts of the network is not valid
        for the combined network.

        Args:
            results : list of Results objects
                single process analysis results from .analyse_network or
                .analyse_single_process methods, where each object contains
                partial results for one or multiple processes

        Returns:
            dict
                combined results dict
        """
        for r in results:
            processes = r._processes_analysed
            if utils.conflicting_entries(self.settings, r.settings):
                raise RuntimeError('Can not combine results - analysis '
                                   'settings are not equal.')
            for p in processes:
                # Remove potential partial FDR-corrected results. These are no
                # longer valid for the combined network.
                if self._is_duplicate_process(p):
                    raise RuntimeError('Can not combine results - results for '
                                       'process {0} already exist.'.format(p))
                try:
                    del r.fdr_corrected
                    print('Removing FDR-corrected results.')
                except AttributeError:
                    pass

                try:
                    results_to_add = r.single_target[p]
                except AttributeError:
                    try:
                        results_to_add = r.single_process[p]
                    except AttributeError:
                        raise AttributeError(
                            'Did not find any method attributes to combine '
                            '(.single_proces or .single_target).')
                self._add_single_result(p, results_to_add, r.settings)


class ResultsSingleProcessAnalysis(Results):
    """Store results of single process analysis.

    Provide a container for the results of algorithms for the analysis of
    individual processes (nodes) in a multivariate stochastic process,
    e.g., estimation of active information storage.

    Note that for convenience all dictionaries in this class can additionally
    be accessed using dot-notation: res_network.settings.cmi_estimator
    or res_network.settings['cmi_estimator'].

    Attributes:
        settings : dict
            settings used for estimation of information theoretic measures and
            statistical testing
        data_properties: dict
            data properties, contains

                - n_nodes : int - total number of nodes in the network
                - n_realisations : int - number of samples available for
                  analysis given the settings (e.g., a high maximum lag used in
                  network inference, results in fewer data points available for
                  estimation)
                - normalised : bool - indicates if data were z-standardised
                  before estimation

        processes_analysed : list
            list of analysed processes
        single_process : dict
            results for individual processes, contains for each process

                - ais : float - AIS-value for current process
                - ais_pval : float - p-value of AIS estimate
                - ais_sign : bool - significance of AIS estimate wrt. to the
                  alpha_mi specified in the settings
                - selected_var : list of tuples - variables with significant
                  information about the current value of the process that have
                  been added to the processes past state, a variable is
                  described by the index of the process in the data and its lag
                  in samples
                - current_value : tuple - current value used for analysis,
                  described by target and sample index in the data

        fdr_correction : dict
            FDR-corrected results, see documentation of network inference
            algorithms and stats.network_fdr

    """

    def __init__(self, n_nodes, n_realisations, normalised):
        super().__init__(n_nodes, n_realisations, normalised)
        self.single_process = {}
        self.processes_analysed = []
        self._add_fdr(None)

    @property
    def processes_analysed(self):
        """Get index of the current_value."""
        return self._processes_analysed

    @processes_analysed.setter
    def processes_analysed(self, processes):
        self._processes_analysed = processes

    def _add_single_result(self, process, results, settings):
        """Add analysis result for a single process."""
        self._check_result(process, settings)
        self.settings.update(DotDict(settings))
        self.single_process[process] = DotDict(results)
        self.processes_analysed = list(self.single_process.keys())

    def _add_fdr(self, fdr, alpha=None, correct_by_target=None, constant=None):
        """Add settings and results of FDR correction"""
        # Add settings of FDR-correction
        self.settings['alpha_fdr'] = alpha
        self.settings['fdr_correct_by_target'] = correct_by_target
        self.settings['fdr_constant'] = constant
        # Add results of FDR-correction. FDR-correction can be None if
        # correction is impossible due to the number of permutations in
        # individual analysis being too low to allow for individual p-values
        # to reach the FDR-thresholds. Add empty results in that case.
        if fdr is None:
            self.fdr_correction = DotDict()
        else:
            self.fdr_correction = DotDict(fdr)

    def single_process_key(self, process, key, fdr=False):
        # Return required key from required single_process dictionary, dealing
        # with the FDR at a high level
        if process not in self.processes_analysed:
            raise RuntimeError('No results for process {0}.'.format(process))
        if fdr:
            try:
                single_process_dict = self.fdr_correction[process]
            except AttributeError:
                raise RuntimeError('No FDR-corrected results have been added.')
            except KeyError:
                raise RuntimeError(
                    'No FDR-corrected results for process {0}.'.format(process))
        else:
            try:
                single_process_dict = self.single_process[process]
            except AttributeError:
                raise RuntimeError('No results have been added.')
            except KeyError:
                raise RuntimeError(
                    'No results for process {0}.'.format(process))

        return single_process_dict[key]

    def get_significant_processes(self, fdr=False):
        """Return statistically-significant processes.

        Indicates for each process whether AIS is statistically significant
        (equivalent to the adjacency matrix returned for network inference)

        Args:
            fdr : bool [optional]
                print FDR-corrected results, see documentation of network
                inference algorithms and stats.network_fdr (default=False)

        Returns:
            numpy array
                Statistical significance for each process
        """

        significant_processes = np.array(
                [self.single_process_key(process=p, key='ais_sign', fdr=fdr)
                 for p in self.processes_analysed],
                dtype=bool
            )

        return significant_processes


class ResultsNetworkAnalysis(Results):

    def __init__(self, n_nodes, n_realisations, normalised):
        super().__init__(n_nodes, n_realisations, normalised)
        self.single_target = {}
        self.targets_analysed = []

    @property
    def targets_analysed(self):
        """Get index of the current_value."""
        return self._processes_analysed

    @targets_analysed.setter
    def targets_analysed(self, targets):
        self._processes_analysed = targets

    def _add_single_result(self, target, results, settings):
        """Add analysis result for a single target."""
        self._check_result(target, settings)
        # Add results
        self.settings.update(DotDict(settings))
        self.single_target[target] = DotDict(results)
        self.targets_analysed = list(self.single_target.keys())

    def single_target_key(self, target, key, fdr=False):
        # Return required key from required single_target dictionary, dealing
        # with the FDR at a high level
        if target not in self.targets_analysed:
            raise RuntimeError('No results for target {0}.'.format(target))
        if fdr:
            try:
                single_target_dict = self.fdr_correction[target]
            except AttributeError:
                raise RuntimeError('No FDR-corrected results have been added.')
            except KeyError:
                raise RuntimeError(
                    'No FDR-corrected results for target {0}.'.format(target))
        else:
            try:
                single_target_dict = self.single_target[target]
            except AttributeError:
                raise RuntimeError('No results have been added.')
            except KeyError:
                raise RuntimeError(
                    'No results for target {0}.'.format(target))

        return single_target_dict[key]

    def get_target_sources(self, target, fdr=False):
        """Return list of sources (parents) for given target.

        Args:
            target : int
                target index
            fdr : bool [optional]
                if True, sources are returned for FDR-corrected results
                (default=False)
        """
        return np.unique(np.array(
            [s[0] for s in (self.single_target_key(
                target, 'selected_vars_sources', fdr))]
        ))


class ResultsNetworkInference(ResultsNetworkAnalysis):
    """Store results of network inference.

    Provide a container for results of network inference algorithms, e.g.,
    MultivariateTE or Bivariate TE.

    Note that for convenience all dictionaries in this class can additionally
    be accessed using dot-notation: res_network.settings.cmi_estimator
    or res_network.settings['cmi_estimator'].

    Attributes:
        settings : dict
            settings used for estimation of information theoretic measures and
            statistical testing
        data_properties: dict
            data properties, contains

                - n_nodes : int - total number of nodes in the network
                - n_realisations : int - number of samples available for
                  analysis given the settings (e.g., a high maximum lag used in
                  network inference, results in fewer data points available for
                  estimation)
                - normalised : bool - indicates if data were z-standardised
                  before the estimation

        targets_analysed : list
            list of analysed targets
        single_target : dict
            results for individual targets, contains for each target

                - omnibus_te : float - TE-value for joint information transfer
                  from all sources into the target
                - omnibus_pval : float - p-value of omnibus information
                  transfer into the target
                - omnibus_sign : bool - significance of omnibus information
                  transfer wrt. to the alpha_omnibus specified in the settings
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

        fdr_correction : dict
            FDR-corrected results, see documentation of network inference
            algorithms and stats.network_fdr

    """

    def __init__(self, n_nodes, n_realisations, normalised):
        super().__init__(n_nodes, n_realisations, normalised)
        self._add_fdr(None)

    def _add_fdr(self, fdr, alpha=None, correct_by_target=None, constant=None):
        """Add settings and results of FDR correction"""
        # Add settings of FDR-correction
        self.settings['alpha_fdr'] = alpha
        self.settings['fdr_correct_by_target'] = correct_by_target
        self.settings['fdr_constant'] = constant
        # Add results of FDR-correction. FDR-correction can be None if
        # correction is impossible due to the number of permutations in
        # individual analysis being too low to allow for individual p-values
        # to reach the FDR-thresholds. Add empty results in that case.
        if fdr is None:
            self.fdr_correction = DotDict()
        else:
            self.fdr_correction = DotDict(fdr)

    def _get_inference_measure(self, target):
        """ """
        if 'selected_sources_te' in self.single_target[target]:
            return self.single_target[target].selected_sources_te
        elif 'selected_sources_mi' in self.single_target[target]:
            return self.single_target[target].selected_sources_mi
        else:
            raise KeyError('No entry with network inference measure found for '
                           'current target')

    def get_target_delays(self, target, criterion='max_te', fdr=False):
        """Return list of information-transfer delays for a given target.

        Return a list of information-transfer delays for a given target.
        Information-transfer delays are determined by the lag of the variable
        in a source past that has the highest information transfer into the
        target process. There are two ways of identifying the variable with
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
            criterion : str [optional]
                use maximum TE value ('max_te') or p-value ('max_p') to
                determine the source-target delay (default='max_te')

        Returns:
            numpy array
                Information-transfer delays for each source
        """
        
        sources = self.get_target_sources(target=target, fdr=fdr)
        delays = np.zeros(sources.shape[0]).astype(int)

        # Get the source index for each past source variable of the target
        all_vars_sources = np.array([x[0] for x in self.single_target_key(
            target=target, key='selected_vars_sources', fdr=fdr)])
        # Get the lag for each past source variable of the target
        all_vars_lags = np.array([x[1] for x in self.single_target_key(
            target=target, key='selected_vars_sources', fdr=fdr)])
        # Get p-values and TE-values for past source variable
        pval = self.single_target_key(
            target=target, key='selected_sources_pval', fdr=fdr)
        measure = self._get_inference_measure(target)

        # Find delay for each source
        for (ind, s) in enumerate(sources):
            if criterion == 'max_p':
                # Find the minimum p-value amongst the variables in source s
                delays_ind = np.argmin(pval[all_vars_sources == s])
            elif criterion == 'max_te':
                # Find the maximum TE-value amongst the variables in source s
                delays_ind = np.argmax(measure[all_vars_sources == s])

            delays[ind] = all_vars_lags[all_vars_sources == s][delays_ind]

        return delays

    def get_adjacency_matrix(self, weights, fdr=False):
        """Return adjacency matrix.

        Return adjacency matrix resulting from network inference. The adjacency
        matrix can either be generated from FDR-corrected results or
        uncorrected results. Multiple options for the weight are available.

        Args:
            weights: str
                can either be

                - 'max_te_lag': the weights represent the source -> target
                   lag corresponding to the maximum tranfer entropy value
                   (see documentation for method get_target_delays for details)
                - 'max_p_lag': the weights represent the source -> target
                   lag corresponding to the maximum p-value
                   (see documentation for method get_target_delays for details)
                - 'vars_count': the weights represent the number of
                   statistically-significant source -> target lags
                - 'binary': return unweighted adjacency matrix with binary
                   entries
                   
                   - 1 = significant information transfer;
                   - 0 = no significant information transfer.

            fdr : bool [optional]
                use FDR-corrected results (default=False)
        """

        adjacency_matrix = np.zeros(
            (self.data_properties.n_nodes, self.data_properties.n_nodes),
            dtype=int)

        if weights == 'max_te_lag':
            for t in self.targets_analysed:
                sources = self.get_target_sources(target=t, fdr=fdr)
                delays = self.get_target_delays(target=t,
                                                criterion='max_te',
                                                fdr=fdr)
                if sources.size:
                    adjacency_matrix[sources, t] = delays
        elif weights == 'max_p_lag':
            for t in self.targets_analysed:
                sources = self.get_target_sources(target=t, fdr=fdr)
                delays = self.get_target_delays(target=t,
                                                criterion='max_p',
                                                fdr=fdr)
                if sources.size:
                    adjacency_matrix[sources, t] = delays
        elif weights == 'vars_count':
            for t in self.targets_analysed:
                for s in self.single_target_key(target=t,
                                                key='selected_vars_sources',
                                                fdr=fdr):
                    adjacency_matrix[s[0], t] += 1
        elif weights == 'binary':
            for t in self.targets_analysed:
                for s in self.single_target_key(target=t,
                                                key='selected_vars_sources',
                                                fdr=fdr):
                    adjacency_matrix[s[0], t] = 1
        else:
            raise RuntimeError('Invalid weights value')

        return adjacency_matrix

    def print_edge_list(self, weights, fdr=False):
        """Print results of network inference to console.

        Print edge list resulting from network inference to console.
        Output may look like this:

            0 -> 1, max_te_lag = 2
            0 -> 2, max_te_lag = 3
            0 -> 3, max_te_lag = 2
            3 -> 4, max_te_lag = 1
            4 -> 3, max_te_lag = 1

        The edge list can either be generated from FDR-corrected results
        or uncorrected results. Multiple options for the weight
        are available (see documentation of method get_adjacency_matrix for
        details).

        Args:
            weights: str
                link weights (see documentation of method get_adjacency_matrix
                for details)

            fdr : bool [optional]
                print FDR-corrected results (default=False)
        """
        adjacency_matrix = self.get_adjacency_matrix(weights=weights, fdr=fdr)
        self._print_edge_list(adjacency_matrix, weights=weights)

    def export_brain_net_viewer(self, mni_coord, file_name, weights, fdr=False,
                                **kwargs):
        """Export network to BrainNet Viewer.

        Export networks to BrainNet Viewer (project home page:
        http://www.nitrc.org/projects/bnv/). BrainNet Viewer is a MATLAB
        toolbox offering brain network visualisation (e.g., 'glass' brains).
        The function creates text files *.node and *.edge, containing
        information on node location (in MNI coordinates), directed edges, node
        color and size.

        References:

        - Xia, M., Wang, J., & He, Y. (2013). BrainNet Viewer: A Network
          Visualization Tool for Human Brain Connectomics. PLoS ONE 8(7):
          e68910. https://doi.org/10.1371/journal.pone.0068910

        Args:
            mni_coord : numpy array
                MNI coordinates (x,y,z) of the sources, array with size [n 3],
                where n is the number of nodes
            file_name : str
                file name for output files *.node and *.edge, including the
                path to the file
            weights : str
                weights for the adjacency matrix (see documentation of method
                get_adjacency_matrix for details)
            fdr : bool [optional]
                use FDR-corrected results (default=False)
            labels : array type of str [optional]
                list of node labels of length n, description or label for each
                node. Note that labels can't contain spaces (causes BrainNet to
                crash), the function will remove any spaces from labels
                (default=no labels)
            node_color : array type of colors [optional]
                BrainNet gives you the option to color nodes according to the
                values in this vector (length n), see BrainNet Manual
            node_size : array type of int [optional]
                BrainNet gives you the option to size nodes according to the
                values in this array (length n), see BrainNet Manual
        """
        adjacency_matrix = self.get_adjacency_matrix(weights=weights, fdr=fdr)
        self._export_brain_net(adjacency_matrix, mni_coord, file_name,
                               fdr=False, **kwargs)

    def export_networkx_graph(self, weights, fdr=False):
        """Generate networkx graph object for an inferred network.

        Generate a weighted, directed graph object from the network of inferred
        (multivariate) interactions (e.g., multivariate TE), using the networkx
        class for directed graphs (DiGraph). Multiple options for the weight
        are available (see documentation of method get_adjacency_matrix for
        details).

        Args:
            weights : str
                weights for the adjacency matrix (see documentation of method
                get_adjacency_matrix for details)
            fdr : bool [optional]
                use FDR-corrected results

        Returns:
            DiGraph object
                instance of a directed graph class from the networkx
                package (DiGraph)
        """
        adjacency_matrix = self.get_adjacency_matrix(weights=weights, fdr=fdr)
        return self._export_to_networkx(adjacency_matrix, weights)

    def export_networkx_source_graph(self, target,
                                     sign_sources=True, fdr=False):
        """Generate graph object of source variables for a single target.

        Generate a graph object from the network of (multivariate)
        interactions (e.g., multivariate TE) between single source variables
        and a target process using the networkx class for directed graphs
        (DiGraph). The graph shows the information transfer between individual
        source variables and the target. Each node is a tuple with the
        following format: (process index, sample index).

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

        graph = nx.DiGraph()

        current_value = self.single_target_key(
                target=target, key='current_value', fdr=fdr)
        # Add the target as a node and add omnibus p-value as an attribute
        # of the target node
        graph.add_node(current_value,
                       omnibus_te=self.single_target_key(
                                    target=target, key='omnibus_te', fdr=fdr),
                       omnibus_sign=self.single_target_key(
                                    target=target, key='omnibus_sign', fdr=fdr)
                       )
        # Get selected source variables
        selected_vars_sources = self.single_target_key(
            target=target, key='selected_vars_sources', fdr=fdr)
        # Get selected target variables
        selected_vars_target = self.single_target_key(
            target=target, key='selected_vars_target', fdr=fdr)

        if sign_sources:  # Add only significant past variables as nodes.
            graph.add_nodes_from(selected_vars_sources)
            graph.add_nodes_from(selected_vars_target)
        else:   # Add all tested past variables as nodes.
            # Get all sample indices.
            samples_tested = np.arange(
                current_value[1] - self.settings.min_lag_sources,
                current_value[1] - self.settings.max_lag_sources,
                -self.settings.tau_sources)
            # Get source indices
            sources_tested = self.single_target_key(
                target=target, key='sources_tested', fdr=fdr)
            # Create tuples from source and sample indices
            tested_vars_sources = [i for i in it.product(
                sources_tested, samples_tested)]
            graph.add_nodes_from(tested_vars_sources)

        # Add edges from selected target variables to the target.
        for v in selected_vars_target:
            graph.add_edge(v, current_value)
        
        # Get TE and p-values fro selected source variables
        selected_sources_te = self.single_target_key(
            target=target, key='selected_sources_te', fdr=fdr)
        selected_sources_pval = self.single_target_key(
            target=target, key='selected_sources_pval', fdr=fdr)
        # Add edges from selected source variables to the target.
        # Also add TE and p-value as edge attributes
        for (ind, v) in enumerate(selected_vars_sources):
            graph.add_edge(v, current_value,
                           te=selected_sources_te[ind],
                           pval=selected_sources_pval[ind]
                           )
        return graph


class ResultsPartialInformationDecomposition(ResultsNetworkAnalysis):
    """Store results of Partial Information Decomposition (PID) analysis.

    Provide a container for results of Partial Information Decomposition (PID)
    algorithms.

    Note that for convenience all dictionaries in this class can additionally
    be accessed using dot-notation: res_pid.single_target[2].source_1
    or res_pid.single_target[2].['source_1'].

    Attributes:
        settings : dict
            settings used for estimation of information theoretic measures and
            statistical testing
        data_properties: dict
            data properties, contains

                - n_nodes : int - total number of nodes in the network
                - n_realisations : int - number of samples available for
                  analysis given the settings (e.g., a high maximum lag used in
                  network inference, results in fewer data points available for
                  estimation)
                - normalised : bool - indicates if data were z-standardised
                  before the estimation

        single_target : dict
            results for individual targets, contains for each target

                - source_1 : tuple - source variable 1
                - source_2 : tuple - source variable 2
                - s1_unq : float - unique information in source 1
                - s2_unq : float - unique information in source 2
                - syn_s1_s2 : float - synergistic information in sources 1
                  and 2
                - shd_s1_s2 : float - shared information in sources 1 and 2
                - s1_unq_sign : float - TODO
                - s2_unq_sign : float - TODO
                - s1_unq_p_val : float - TODO
                - s2_unq_p_val : float - TODO
                - syn_sign : float - TODO
                - syn_p_val : float - TODO
                - shd_sign : float - TODO
                - shd_p_val : float - TODO
                - current_value : tuple - current value used for analysis,
                  described by target and sample index in the data


        targets_analysed : list
            list of analysed targets
    """

    def __init__(self, n_nodes, n_realisations, normalised):
        super().__init__(n_nodes, n_realisations, normalised)


class ResultsNetworkComparison(ResultsNetworkAnalysis):
    """Store results of network comparison.

    Provide a container for results of network comparison algorithms.

    Note that for convenience all dictionaries in this class can additionally
    be accessed using dot-notation: res_network.settings.cmi_estimator
    or res_network.settings['cmi_estimator'].

    Attributes:
        settings : dict
            settings used for estimation of information theoretic measures and
            statistical testing

        data_properties: dict
            data properties, contains

                - n_nodes : int - total number of nodes in the network
                - n_realisations : int - number of samples available for
                  analysis given the settings (e.g., a high maximum lag used in
                  network inference, results in fewer data points available for
                  estimation)
                - normalised : bool - indicates if data were z-standardised
                  before the estimation

        single_target : dict
            results for individual targets, contains for each target

                - selected_vars_sources : numpy array - union of source
                  variables
                - selected_vars_target : numpy array - union of target
                  variables
                - sources : numpy array - list of source processes

        surrogate_distribution : dict
            surrogate distribution for each target
        targets_analysed : list
            list of analysed targets
    """

    def __init__(self, n_nodes, n_realisations, normalised):
        super().__init__(n_nodes, n_realisations, normalised)

    def _add_results(self, union_network, results, settings):
        # Check if results have already been added to this instance.
        if self.settings:
            raise RuntimeWarning('Overwriting existing results.')
        # Add results
        self.settings = DotDict(settings)
        self.targets_analysed = union_network['targets_analysed']
        for t in self.targets_analysed:
            self.single_target[t] = DotDict(union_network.single_target[t])
        # self.max_lag = union_network['max_lag']
        self.surrogate_distributions = results['cmi_surr']
        self.ab = results['a>b']
        self.cmi_diff_abs = results['cmi_diff_abs']
        self.pval = results['pval']

    def get_adjacency_matrix(self, weights='comparison'):
        """Return adjacency matrix.

        Return adjacency matrix resulting from network inference.
        Multiple options for the weights are available.

        Args:
            weights : str [optional]
                can either be

                - 'union': all links in the union network, i.e., all
                  links that were tested for a difference

                or return information for links with a significant difference

                - 'comparison': True for links with a significant difference in
                   inferred effective connectivity (default)
                - 'pvalue': absolute differences in inferred effective
                   connectivity for significant links
                - 'diff_abs': absolute difference

        """
        if weights == 'comparison':
            adjacency_matrix = np.zeros(
                (self.data_properties.n_nodes, self.data_properties.n_nodes),
                dtype=bool)
            for t in self.targets_analysed:
                sources = self.get_target_sources(t)
                for (i, s) in enumerate(sources):
                        adjacency_matrix[s, t] = self.ab[t][i]
        elif weights == 'union':
            adjacency_matrix = np.zeros(
                (self.data_properties.n_nodes, self.data_properties.n_nodes),
                dtype=int)
            for t in self.targets_analysed:
                sources = self.get_target_sources(t)
                if sources.size:
                    adjacency_matrix[sources, t] = 1
        elif weights == 'diff_abs':
            adjacency_matrix = np.zeros(
                (self.data_properties.n_nodes, self.data_properties.n_nodes),
                dtype=float)
            for t in self.targets_analysed:
                sources = self.get_target_sources(t)
                for (i, s) in enumerate(sources):
                    adjacency_matrix[s, t] = self.cmi_diff_abs[t][i]
        elif weights == 'pvalue':
            adjacency_matrix = np.ones(
                (self.data_properties.n_nodes, self.data_properties.n_nodes),
                dtype=float)
            for t in self.targets_analysed:
                sources = self.get_target_sources(t)
                for (i, s) in enumerate(sources):
                    adjacency_matrix[s, t] = self.pval[t][i]

        # self._print_edge_list(adjacency_matrix, weights=weights)
        return adjacency_matrix

    def print_edge_list(self, weights='comparison'):
        """Print results of network comparison to console.

        Print results of network comparison to console. Output looks like this:

            0 -> 1, diff_abs = 0.2
            0 -> 2, diff_abs = 0.5
            0 -> 3, diff_abs = 0.7
            3 -> 4, diff_abs = 1.3
            4 -> 3, diff_abs = 0.4

        indicating differences in the network inference measure for a link
        source -> target.

        Args:
            weights : str [optional]
                weights for the adjacency matrix (see documentation of method
                get_adjacency_matrix for details)
        """
        adjacency_matrix = self.get_adjacency_matrix(weights=weights)
        self._print_edge_list(adjacency_matrix, weights=weights)

    def export_brain_net_viewer(self, mni_coord, file_name, weights, fdr=False,
                                **kwargs):
        """Export network to BrainNet Viewer.

        Export networks to BrainNet Viewer (project home page:
        http://www.nitrc.org/projects/bnv/). BrainNet Viewer is a MATLAB
        toolbox offering brain network visualisation (e.g., 'glass' brains).
        The function creates text files *.node and *.edge, containing
        information on node location (in MNI coordinates), directed edges, node
        color and size.

        References:

        - Xia, M., Wang, J., & He, Y. (2013). BrainNet Viewer: A Network
          Visualization Tool for Human Brain Connectomics. PLoS ONE 8(7):
          e68910. https://doi.org/10.1371/journal.pone.0068910

        Args:
            mni_coord : numpy array
                MNI coordinates (x,y,z) of the sources, array with size [n 3],
                where n is the number of nodes
            file_name : str
                file name for output files *.node and *.edge, including the
                path to the file
            weights : str
                weights for the adjacency matrix (see documentation of method
                get_adjacency_matrix for details)
            fdr : bool [optional]
                use FDR-corrected results (default=False)
            labels : array type of str [optional]
                list of node labels of length n, description or label for each
                node. Note that labels can't contain spaces (causes BrainNet to
                crash), the function will remove any spaces from labels
                (default=no labels)
            node_color : array type of colors [optional]
                BrainNet gives you the option to color nodes according to the
                values in this vector (length n), see BrainNet Manual
            node_size : array type of int [optional]
                BrainNet gives you the option to size nodes according to the
                values in this array (length n), see BrainNet Manual
        """
        adjacency_matrix = self.get_adjacency_matrix(weights=weights, fdr=fdr)
        self._export_brain_net(adjacency_matrix, mni_coord, file_name,
                               **kwargs)

    def export_networkx_graph(self, weights='comparison'):
        """Generate networkx graph object from network comparison results.

        Generate a weighted, directed graph object from the adjacency matrix
        representing results of network comparison, using the networkx class
        for directed graphs (DiGraph). Multiple options for the weights
        are available (see documentation of method get_adjacency_matrix for
        details).

        Args:
            weights : str [optional]
                weights for the adjacency matrix (see documentation of method
                get_adjacency_matrix for details)

        Returns:
            DiGraph object
                instance of a directed graph class from the networkx
                package (DiGraph)
        """
        adjacency_matrix = self.get_adjacency_matrix(weights=weights)
        return self._export_to_networkx(adjacency_matrix, weights)
