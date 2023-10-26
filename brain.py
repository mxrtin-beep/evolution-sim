


class Neuron:

	def __init__(self, n_inputs):

		self.in_weights = np.randn(n_inputs)


class Brain:

	def __init__(self, genome, n_inner_neurons):

		self.genome = genome
		self.n_inner_neurons = n_inner_neurons