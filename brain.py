

import random
import numpy as np
import math
import networkx as nx
import matplotlib.pyplot as plt


def sigmoid(x):
	return 1 / (1 + math.exp(-x))

class Neuron:

	def __init__(self):
		self.inputs = {} # Map from neuron to weight
		self.activation = 0 
		self.threshold = 0.5 # 0 to 1

	def add_input_neuron(self, input_key, input_weight):
		self.inputs[input_key] = input_weight

	def get_num_connections(self):
		return len(self.inputs)

	def set_activation(self, new_activation):
		self.activation = new_activation

	def get_activation(self):
		return self.activation

	def get_threshold(self):
		return self.threshold

	def get_inputs(self):
		return self.inputs

	def update_threshold(self, change):

		new_threshold = sigmoid(change + self.threshold)
		self.threshold = new_threshold

	def __str__(self):
		s = ''
		for key in self.inputs.keys():
			s += f'\n\t Neuron {key} (A: {self.activation}) (W: {int(self.inputs[key])}) ->'
		return s


class Brain:


	def build_connections(self, genome):

		for gene in genome:

			# gene is a hexadecimal
			gene = int(gene, 16)
			binary_str = f'{gene:0>32b}'
			
			source_type = int(binary_str[0])		# 0: input sensory neuron; 1: internal neuron
			source_id = int(binary_str[1:8])				# which source
			sink_type = int(binary_str[8])				# 0: internal neuron; 1: action
			sink_id = int(binary_str[9:16])			# which sink
			weight = int(binary_str[16:])				# weight (divide by about 8,000)
			
			### Source ###
			if source_type == 0:	# input sensory neuron
				source_idx = source_id % len(self.sensory_neurons)
				source_key = list(self.sensory_neurons.keys())[source_idx]	# 'Age', 'Rnd', ...
			elif source_type == 1:	# internal neuron
				source_idx = source_id % self.n_inner_neurons
				source_key = list(self.inner_neurons.keys())[source_idx]	# 0, 1, ...

			### Sink ###
			if sink_type == 0:	# internal neuron
				sink_idx = sink_id % self.n_inner_neurons
				sink_key = list(self.inner_neurons.keys())[sink_idx]
				sink_neuron = self.inner_neurons[sink_key]
			elif sink_type == 1: # action neuron
				sink_idx = sink_id % len(self.action_neurons)
				sink_key = list(self.action_neurons.keys())[sink_idx]
				sink_neuron = self.action_neurons[sink_key]

			connection_weight = int(str(weight), 2) / 65535

			sink_neuron.add_input_neuron(source_key, connection_weight)
			#print(f'Making Connection from {source_key} to {sink_key} ({sink_neuron}).')

	def __init__(self, genome, n_inner_neurons):

		self.genome = genome

		self.sensory_neurons = {
			'Age': Neuron(),	# age
			'Rnd': Neuron(), 	# random input
			'Blr': Neuron(),	# blockage left-right
			'Osc': Neuron(),	# oscillator
			'Bfd': Neuron(),	# blockage forward
			'Pop': Neuron(),	# population density in immediate area
			'LMx': Neuron(), 	# last movement x
			'LMy': Neuron(),	# last movement y
			'Gen': Neuron(), 	# genetic similarity of fwd neighbor
			'Lx': Neuron(),		# x location
			'Ly': Neuron(), 	# y location
			'BD': Neuron(), 	# nearest border distance
			'Bs': Neuron(),		# bias (always on)
		}

		self.n_inner_neurons = n_inner_neurons

		self.inner_neurons = {}
		for i in range(n_inner_neurons):
			self.inner_neurons[str(i)] = Neuron()


		self.action_neurons = {
			'R+': Neuron(), 	# increase responsiveness
			'R-': Neuron(), 	# decrease responsiveness
			'O+': Neuron(),		# increase oscillatory delay
			'O-': Neuron(),		# decrease oscillator delay
			'Mfd': Neuron(), 	# move forward
			'Mrn': Neuron(), 	# move random
			'Mrv': Neuron(),	# move reverse
			'Mrt': Neuron(),	# move right
			'Mlt': Neuron(),	# move left
			'MXf': Neuron(),	# move east
			'MXr': Neuron(),	# move west
			'MYf': Neuron(),	# move south
			'MYr': Neuron(),	# move north
		}

		self.build_connections(genome)

	# Sets new activation of sensory neurons
	def activate_sensory_neuron(self, key, new_activation):
		self.sensory_neurons[key].set_activation(new_activation)


	# Updates neuron activations
	def forward_pass(self):

		### Update Inner Neurons
		for key in self.inner_neurons.keys():
			neuron = self.inner_neurons[key]
			inputs = neuron.get_inputs()

			new_activation = 0

			for input_key in inputs.keys():
				weight = inputs[input_key]

				if len(input_key) == 1: # inner neuron
					activation = self.inner_neurons[input_key].get_activation()
				else:	# sensory neuron
					activation = self.sensory_neurons[input_key].get_activation()

				new_activation += (weight * activation)

			neuron.set_activation(np.tanh(new_activation))

		### Update Action Neurons (same code)
		for key in self.action_neurons.keys():
			neuron = self.action_neurons[key]
			inputs = neuron.get_inputs()

			new_activation = 0

			for input_key in inputs.keys():
				weight = inputs[input_key]

				if len(input_key) == 1: # inner neuron
					activation = self.inner_neurons[input_key].get_activation()
				else:	# sensory neuron
					activation = self.sensory_neurons[input_key].get_activation()

				new_activation += (weight * activation)

			neuron.set_activation(np.tanh(new_activation))



	def get_decisions(self):

		action_list = []

		for key in self.action_neurons.keys():
			
			action_neuron_activation = self.action_neurons[key].get_activation()
			action_neuron_threshold = self.action_neurons[key].get_threshold()

			if action_neuron_activation > action_neuron_threshold:
				action_list.append(key)

		return action_list

	def update_responsiveness(self, change):

		for key in self.sensory_neurons.keys():
			neuron = self.sensory_neurons[key]
			neuron.update_threshold(change)

		for key in self.inner_neurons.keys():
			neuron = self.inner_neurons[key]
			neuron.update_threshold(change)

		for key in self.action_neurons.keys():
			neuron = self.action_neurons[key]
			neuron.update_threshold(change)

	def __str__(self):
		s = '\n'

		for key in self.sensory_neurons.keys():
			neuron = self.sensory_neurons[key]
			s += f'Sensory Neuron {key}; Activation {neuron.get_activation()}\n'

		for key in self.inner_neurons.keys():
			neuron = self.inner_neurons[key]
			if neuron.get_num_connections() > 0:
				s += f'Inner Neuron {key}; Activation {neuron.get_activation()}\n'

		for key in self.action_neurons.keys():
			neuron = self.action_neurons[key]
			#if neuron.get_num_connections() > 0:
			s += f'Action Neuron {key}; Activation {neuron.get_activation()}\n'

		return s


	def draw(self):


		G = nx.DiGraph()

		sensory_x, sensory_y = 0, 0
		inner_x, inner_y = 1000, 0
		action_x, action_y = 2000, 0
		y_offset = 250
		
		color_map = []
		sensory_color = 'yellow'
		inner_color = 'gray'
		action_color = 'cyan'

		# Add sensory neuron
		for key in self.sensory_neurons.keys():
			G.add_node(key, pos=(sensory_x, sensory_y))
			sensory_y += y_offset
			color_map.append(sensory_color)
		
		for key in self.inner_neurons.keys():
			G.add_node(key, pos=(inner_x, inner_y))
			color_map.append(inner_color)

			for in_key in self.inner_neurons[key].get_inputs().keys():
				G.add_edges_from([(in_key, key)], weight=round(self.inner_neurons[key].get_inputs()[in_key], 2))
			inner_y += y_offset*3

		for key in self.action_neurons.keys():
			G.add_node(key, pos=(action_x, action_y))
			color_map.append(action_color)

			for in_key in self.action_neurons[key].get_inputs().keys():
				G.add_edges_from([(in_key, key)], weight=round(self.action_neurons[key].get_inputs()[in_key], 2))
			action_y += y_offset



		elarge = [(u, v) for (u, v, d) in G.edges(data=True)]

		pos = nx.get_node_attributes(G, 'pos')
		edge_labels = nx.get_edge_attributes(G, "weight")

		plt.figure(3,figsize=(12,12)) 
		nx.draw_networkx_edges(G, pos, edgelist=elarge, width=1)	
		nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=9, verticalalignment='bottom')
		nx.draw(G, pos, node_color=color_map, node_size=350, with_labels=True)
		plt.savefig('brain.png')
		#plt.show()


