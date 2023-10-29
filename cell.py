
import random
import secrets
from brain import Brain
import numpy as np

class Cell:

	

	def __init__(self, x, y, n_genes, n_inner_neurons, id_number, environment):

		dirs = [-1, 0, 1]

		self.x_pos = x
		self.y_pos = y

		self.x_dir = dirs[random.randint(0, len(dirs) - 1)]
		self.y_dir = dirs[random.randint(0, len(dirs) - 1)]

		self.genome = []

		for i in range(n_genes):
			self.genome.append(secrets.token_hex(4))	# 4 genes by 4 bytes = 16 bytes, 128 bits

		self.n_inner_neurons = n_inner_neurons
		self.brain = Brain(self.genome, n_inner_neurons)

		self.id_number = id_number

		self.environment = environment

		self.age = 0


	### GETTERS ###

	def get_x(self):
		return self.x_pos

	def get_y(self):
		return self.y_pos

	def get_id(self):
		return self.id_number

	def get_genome(self):
		return self.genome

	def get_color(self):

		gene_max = int('ffffffff', 16)
		color_max = 255

		return (
				int(int(self.genome[0], 16)/gene_max*color_max), 
				int(int(self.genome[1], 16)/gene_max*color_max),
				int(int(self.genome[2], 16)/gene_max*color_max),
			)


	def age_up(self):
		self.age += 1


	def set_genome(self, new_genome):
		self.genome = new_genome

	def set_position(self, new_x, new_y):
		self.x_pos = new_x
		self.y_pos = new_y

	def set_id(self, new_id):
		self.id_number = new_id


	def randomize_direction(self):
		dirs = [-1, 0, 1]
		self.x_dir = dirs[random.randint(0, len(dirs) - 1)]
		self.y_dir = dirs[random.randint(0, len(dirs) - 1)]

	### BRAIN METHODS ###

	def activate_sensory_neurons(self):

		self.brain.activate_sensory_neuron('Age', self.age / 500) # Age
		self.brain.activate_sensory_neuron('Rnd', random.uniform(0, 1)) # Random input
		self.brain.activate_sensory_neuron('Blr', self.calculate_left_right_blockage_()) # Left-Right Blockage
		self.brain.activate_sensory_neuron('Osc', self.age % 2)	# Oscillator
		self.brain.activate_sensory_neuron('Bfd', self.calculate_forward_blockage_()) # Blockage forward
		self.brain.activate_sensory_neuron('Pop', self.calculate_population_density_()) # Population density
		self.brain.activate_sensory_neuron('LMx', self.x_dir) # Last movement (direction) x
		self.brain.activate_sensory_neuron('LMy', self.y_dir) # Last movement (direction) y
		self.brain.activate_sensory_neuron('Gen', self.calculate_genetic_similarity_of_forward_neighbor()) # Genetic similarity of forward neighbor
		self.brain.activate_sensory_neuron('Lx', self.x_pos / (self.environment.get_x_size() - 1)) # X position
		self.brain.activate_sensory_neuron('Ly', self.y_pos / (self.environment.get_y_size() - 1)) # Y position
		self.brain.activate_sensory_neuron('BD', self.get_nearest_border_distance_()) # nearest border
		self.brain.activate_sensory_neuron('Bs', 1) # bias

	def think(self):
		self.brain.forward_pass()

	def execute_decision(self):

		decision_list = self.brain.get_decisions()
		dirs = [-1, 0, 1]

		for decision in decision_list:
			# Movement actions
			if decision == 'Mfd': # forward
				self.move_cell_(self.x_dir, self.y_dir)
			elif decision == 'Mrn': # random
				self.move_cell_(dirs[random.randint(0, 2)], dirs[random.randint(0, 2)])
			elif decision == 'Mrv': # reverse
				self.move_cell_(-self.x_dir, -self.y_dir)
			elif decision == 'Mrt': # right
				self.move_cell_(self.y_dir, -self.x_dir)
			elif decision == 'Mlt': # left
				self.move_cell_(-self.y_dir, self.x_dir)
			elif decision == 'MXf': # east
				self.move_cell_(1, 0)
			elif decision == 'MXr': # west
				self.move_cell_(-1, 0)
			elif decision == 'MYf': # south
				self.move_cell_(0, 1)
			elif decision == 'MYr':	# north
				self.move_cell_(0, -1)

			elif decision == 'R+':	# increase responsiveness
				self.brain.update_responsiveness(1)
			elif decision == 'R-':	# increase responsiveness
				self.brain.update_responsiveness(-1)
	
		return decision_list


	### HELPER METHODS ###

	def get_coordinate_info_(self, x, y):
		
		if x >= 0 and x < self.environment.get_x_size():
			if y >= 0 and y < self.environment.get_y_size():
				return int(self.environment.get_grid()[x, y])
		return -1

	def calculate_left_right_blockage_(self):

		blockage = 0
		left_x = self.x_pos - self.y_dir
		left_y = self.y_pos + self.x_dir
		left_info = self.get_coordinate_info_(left_x, left_y)

		right_x = self.x_pos + self.y_dir
		right_y = self.y_pos - self.x_dir
		right_info = self.get_coordinate_info_(right_x, right_y)

		if left_info == 0:
			blockage -= 0.5
		else:
			blockage += 0.5

		if right_info == 0:
			blockage -= 0.5
		else:
			blockage += 0.5

		return blockage

	def calculate_forward_blockage_(self):

		fwd_x = self.x_pos + self.x_dir
		fwd_y = self.y_pos + self.y_dir

		fwd_info = self.get_coordinate_info_(fwd_x, fwd_y)

		if fwd_info == 0:
			return 0
		return 1

	def calculate_population_density_(self):

		total_nearby_population = -1 # don't count self
		radius = 2
		for i in range(-radius, radius+1):
			for j in range(-radius, radius+1):
				x = self.x_pos + i
				y = self.y_pos + j
				info = self.get_coordinate_info_(x, y)
				if info > 0:
					total_nearby_population += 1

		return total_nearby_population / (2 * radius)**2

	def calculate_genetic_similarity_of_forward_neighbor(self):

		fwd_x = self.x_pos + self.x_dir
		fwd_y = self.y_pos + self.y_dir
		fwd_info = self.get_coordinate_info_(fwd_x, fwd_y)

		if fwd_info > self.environment.get_population():
			print(fwd_info, self.environment.get_population())
			quit()

		if fwd_info > 0:
			fwd_cell_genome = self.environment.get_cells()[fwd_info - 1].get_genome()
			percent_similar = get_genetic_similarity(fwd_cell_genome, self.genome)
			return percent_similar*2 - 1 # from -1 to 1

		return 0


	def get_nearest_border_distance_(self):

		x_d, y_d = self.x_pos, self.y_pos
		x_i, y_i = self.x_pos, self.y_pos
		x_size = self.environment.get_x_size()
		y_size = self.environment.get_y_size()

		distance = 0

		while x_d > 0 and y_d > 0 and x_i < x_size and y_i < y_size:
			x_d -= 1
			y_d -= 1
			x_i += 1
			y_i += 1
			distance += 1

		return (distance-1) / (max(x_size, y_size)-1)


	def is_valid_move_x(self, x_movement):
		return self.x_pos + x_movement >= 0 and self.x_pos + x_movement < self.environment.get_x_size() and self.environment.get_grid()[self.x_pos + x_movement, self.y_pos] == 0

	def is_valid_move_y(self, y_movement):
		return self.y_pos + y_movement >= 0 and self.y_pos + y_movement < self.environment.get_y_size() and self.environment.get_grid()[self.x_pos, self.y_pos + y_movement] == 0

	def move_cell_(self, x_movement, y_movement):

		# Move X
		if x_movement != 0 and self.is_valid_move_x(x_movement):
			self.x_pos += x_movement # update position
			self.environment.grid[self.x_pos, self.y_pos] = self.id_number # update grid
			self.environment.grid[self.x_pos - x_movement, self.y_pos] = 0
			self.x_dir = int(x_movement / np.abs(x_movement)) # update direction (-1, 0, or 1)
		else:
			self.x_dir = 0

		# Move Y
		if y_movement != 0 and self.is_valid_move_y(y_movement):
			self.y_pos += y_movement
			self.environment.grid[self.x_pos, self.y_pos] = self.id_number
			self.environment.grid[self.x_pos, self.y_pos - y_movement] = 0
			self.y_dir = int(y_movement / np.abs(y_movement))
		else:
			self.y_dir = 0

	### REPRODUCTION ###

	def get_mutated_genome(self, mutation_rate):

		nucleotides = '0123456789abcdef'
		genome_mut = []

		for gene in self.genome:
			new_gene = ''

			for i in range(len(gene)):
				mutation_event = random.random() # 0 to 1

				if mutation_event > mutation_rate: # no mutation
					new_gene += gene[i]
				else:
					new_gene += nucleotides[random.randint(0, len(nucleotides)-1)]

			assert(len(new_gene) == len(gene))
			genome_mut.append(new_gene)

		return genome_mut


	def mutate_genome(self, mutation_rate):

		genome_mut = self.get_mutated_genome(mutation_rate)
		self.genome = genome_mut
		self.brain = Brain(self.genome, self.n_inner_neurons)


	### TO STRING ###

	def __str__(self):
		s = f'Cell {self.id_number}\n Position {self.x_pos},{self.y_pos}\n Genome: {self.genome}\n Brain: {self.brain}\n'
		return s



	

# percent similar
def get_genetic_similarity(genome1, genome2):

	n_same_bases = 0
	total_genome_length = 0

	for i in range(len(genome1)):
		gene1 = str(genome1[i])
		gene2 = str(genome2[i])

		assert(len(gene1) == len(gene2))

		total_genome_length += len(gene1)

		for j in range(len(gene1)):
			if gene1[j] == gene2[j]:
				n_same_bases += 1

	return n_same_bases / total_genome_length


